package internal

import (
	"context"
	"encoding/json"
	"fmt"
	"strconv"
	"time"

	"github.com/ianwong123/kubernetes-cost-optimiser/metric-hub/internal/queue"
	"github.com/redis/go-redis/v9"
)

type AggregatorInterface interface {
	SaveCostPayload(p *CostPayload) error
	FetchPayload(p *ForecastPayload) error
}

type Aggregator struct {
	Client *redis.Client
	Queue  queue.QueueClient
}

const (
	LatestCostKey = "cost:latest"
	AgentQueueKey = "queue:agent:jobs"
)

func NewAggregator(redisAddr string, redisPass string) *Aggregator {
	rdb := redis.NewClient(&redis.Options{
		Addr:     redisAddr,
		Password: redisPass,
		DB:       0,
	})

	queueTool := queue.NewRedisQueue(rdb)

	return &Aggregator{
		Client: rdb,
		Queue:  queueTool,
	}
}

// Marshal payload and save to redis
// Key - cost:latest
// Value - <payload>
func (a *Aggregator) SaveCostPayload(p *CostPayload) error {
	bg := context.Background()
	jsonData, err := json.Marshal(p)
	if err != nil {
		return fmt.Errorf("[Failed] to marshal payload: %w", err)
	}

	err = a.Client.Set(context.Background(), LatestCostKey, jsonData, 0).Err()
	if err != nil {
		return fmt.Errorf("[Failed] SET redis: %w", err)
	}

	ctx, cancel := context.WithTimeout(bg, 10*time.Second)

	go func() {
		defer cancel()
		a.CheckCostThreshold(ctx, p)
	}()

	return nil
}

func (a *Aggregator) CheckCostThreshold(ctx context.Context, p *CostPayload) {
	fmt.Printf("[Background] Starting threshold check for %d deployments\n", len(p.Deployments))

	ns := p.Namespace
	clusterInfo := p.ClusterInfo

	for _, deployment := range p.Deployments {
		select {
		case <-ctx.Done():
			fmt.Printf("Threshold check cancelled")
			return
		default:
		}

		reqCpu := deployment.CurrentRequests.CPUCores
		useCpu := deployment.CurrentUsage.CPUCores
		reqMem := deployment.CurrentRequests.MemoryMB
		useMem := deployment.CurrentUsage.MemoryMB

		if reqCpu == 0 || reqMem == 0 {
			continue
		}

		var wasteCpu, utilCpu, wasteMem, utilMem float64

		if reqCpu > 0 {
			wasteCpu = (reqCpu - useCpu) / reqCpu
			utilCpu = useCpu / reqCpu
		}

		if reqMem > 0 {
			wasteMem = (reqMem - useMem) / reqMem
			utilMem = useMem / reqMem
		}

		// Prioritise memory
		// one reason is sufficient for triggering agent
		if wasteMem > 0.5 {
			a.handleTrigger(ctx, deployment, "High Memory Waste", ns, clusterInfo)
		} else if utilMem > 0.85 {
			a.handleTrigger(ctx, deployment, "High Memory Risk", ns, clusterInfo)
		} else if wasteCpu > 0.5 {
			a.handleTrigger(ctx, deployment, "High CPU Waste", ns, clusterInfo)
		} else if utilCpu > 0.85 {
			a.handleTrigger(ctx, deployment, "High CPU Risk", ns, clusterInfo)
		}
	}
}

// Handle trigger cooldown
// Key: trigger:cooldown:<deployment name>
// Value: timestamp
func (a *Aggregator) handleTrigger(ctx context.Context, c CostDeployment, reason string, ns string, info ClusterInfo) {
	// define key
	key := fmt.Sprintf("trigger:cooldown:%s", c.Name)

	// check redis for the last timestamp
	// return a string and convert to int64
	lastTriggerStr, err := a.Client.Get(ctx, key).Result()

	// handle case if first time triggering
	if err == redis.Nil {
		a.executePush(ctx, key, c, reason, ns, info)
		return
	} else if err != nil {
		fmt.Printf("Redis error %v\n", err)
		return
	}

	// conver string to int64
	lastTrigger, err := strconv.ParseInt(lastTriggerStr, 10, 64)
	if err != nil {
		fmt.Printf("Failed to parse timstamp %v\n", err)
		return
	}

	currentTime := time.Now().Unix()

	// if last trigger <30 mins ago, drop, stop, dont push to queue
	if currentTime-lastTrigger < 1800 {
		fmt.Printf("Cooldown active for %s. Skipping.\n", c.Name)
		return
	}

	// Proceed to push if cooldown expired
	a.executePush(ctx, key, c, reason, ns, info)
}

// push to queue and update timestamp
func (a *Aggregator) executePush(ctx context.Context, cooldownKey string, c CostDeployment, reason string, ns string, info ClusterInfo) {
	fmt.Printf("Pushing to queue for %s because: %s\n", c.Name, reason)

	// Push to queue
	job := AgentJob{
		Reason:      reason,
		Namespace:   ns,
		Deployment:  c,
		ClusterInfo: info,
	}

	err := a.Queue.PublishJob(ctx, AgentQueueKey, job)
	if err != nil {
		fmt.Printf("Failed to push job: %v\n", err)
		return
	}
	// Update time
	a.Client.Set(ctx, cooldownKey, time.Now().Unix(), 0)
}

// prepare cost key for merging
func (a *Aggregator) FetchPayload(p *ForecastPayload) error {
	bg := context.Background()

	latestCostJSON, err := a.Client.Get(bg, LatestCostKey).Result()

	if err == redis.Nil {
		return fmt.Errorf("cannot process forecast: latest cost data (%s) not found in cache", LatestCostKey)
	} else if err != nil {
		return fmt.Errorf("failed to get redis cost data %w", err)

	}

	ctx, cancel := context.WithTimeout(bg, 10*time.Second)

	go func() {
		defer cancel()
		a.CheckForecastThreshold(ctx, p, latestCostJSON)
	}()
	return nil

}

// check forecast
func (a *Aggregator) CheckForecastThreshold(ctx context.Context, p *ForecastPayload, latestCostJSON string) {
	var costPayload CostPayload
	// unmarshal cost key value back to struct
	if err := json.Unmarshal([]byte(latestCostJSON), &costPayload); err != nil {
		fmt.Printf("failed to unmarshal cost json in background %v", err)
		return
	}

	// convert the cost list into map where key = name
	costMap := make(map[string]CostDeployment)
	for _, costDep := range costPayload.Deployments {
		costMap[costDep.Name] = costDep
	}

	fmt.Printf("Starting forecast merge for %d deployments\n", len(p.Deployments))

	// Merge forecast fields to the correct deployment
	for _, forecastDep := range p.Deployments {
		select {
		case <-ctx.Done():
			fmt.Printf("Forecast check cancelled")
			return
		default:
		}

		if costDep, exists := costMap[forecastDep.Name]; exists {
			a.evaluateForecastLogic(ctx, forecastDep, costDep, costPayload.Namespace, costPayload.ClusterInfo)
		} else {
			fmt.Printf("No cost data found for forecast deployment %v", forecastDep.Name)
		}
	}
}

func (a *Aggregator) evaluateForecastLogic(ctx context.Context, f ForecastDeployment, c CostDeployment, ns string, info ClusterInfo) {
	reqCpu := c.CurrentRequests.CPUCores
	usageCpu := c.CurrentUsage.CPUCores
	predCpu := f.PredictPeak24h.CPUCores

	reqMem := c.CurrentRequests.MemoryMB
	usageMem := c.CurrentRequests.MemoryMB
	predMem := f.PredictPeak24h.MemoryMB

	// cpu logic
	if reqCpu > 0 {
		capacityRiskCpu := predCpu > (reqCpu * 0.9)
		currentWasteCpu := (reqCpu - usageCpu) / reqCpu
		safeDownscaleCpu := currentWasteCpu > 0.4 && predCpu < (reqCpu*0.6)

		if capacityRiskCpu {
			a.executeForecastPush(ctx, c, "Predicted Capacity Risk (CPU)", ns, info, f.PredictPeak24h)
			return
		} else if safeDownscaleCpu {
			a.executeForecastPush(ctx, c, "Predicted Safe Downscale (CPU)", ns, info, f.PredictPeak24h)
			return
		}
	}

	// 2. Memory Logic (If CPU didn't trigger)
	if reqMem > 0 {
		capacityRiskMem := predMem > (reqMem * 0.9)
		currentWasteMem := (reqMem - usageMem) / reqMem
		safeDownscaleMem := currentWasteMem > 0.4 && predMem < (reqMem*0.6)

		if capacityRiskMem {
			a.executeForecastPush(ctx, c, "Predicted Capacity Risk (Memory)", ns, info, f.PredictPeak24h)
			return
		} else if safeDownscaleMem {
			a.executeForecastPush(ctx, c, "Predicted Safe Downscale (Memory)", ns, info, f.PredictPeak24h)
			return
		}
	}
}

func (a *Aggregator) executeForecastPush(ctx context.Context, c CostDeployment, reason string, ns string, info ClusterInfo, prediction Resources) {
	fmt.Printf("Pushing forecast job for %s\n", c.Name)

	c.PredictPeak24h = &prediction

	job := AgentJob{
		Reason:      reason,
		Namespace:   ns,
		Deployment:  c,
		ClusterInfo: info,
	}
	err := a.Queue.PublishJob(ctx, AgentQueueKey, job)
	if err != nil {
		fmt.Printf("Failed to push forecast job: %v\n", err)
	}
}
