package internal

import (
	"context"
	"encoding/json"
	"fmt"
	"strconv"
	"time"

	"github.com/redis/go-redis/v9"
)

type AggregatorInterface interface {
	SaveCostPayload(p *CostPayload) error
}

type Aggregator struct {
	Client *redis.Client
}

func NewAggregator(redisAddr string, redisPass string) *Aggregator {
	rdb := redis.NewClient(&redis.Options{
		Addr:     redisAddr,
		Password: redisPass,
		DB:       0,
	})

	return &Aggregator{
		Client: rdb,
	}
}

const LatestCostKey = "cost:latest"

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
	fmt.Printf("[Background] Starting threshold check for %d deployments", len(p.Deployments))

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

		wasteCpu := (reqCpu - useCpu) / reqCpu
		utilCpu := useCpu / reqCpu

		wasteMem := (reqMem - useMem) / reqMem
		utilMem := useMem / reqMem

		// evaluate cpu logic
		if wasteCpu > 0.5 {
			a.handleTrigger(ctx, deployment, "High CPU Waste")
		} else if utilCpu > 0.85 {
			a.handleTrigger(ctx, deployment, "High CPU Risk")
		}

		// evaluate memory logic
		if wasteMem > 0.5 {
			a.handleTrigger(ctx, deployment, "High Memory Waste")
		} else if utilMem > 0.85 {
			a.handleTrigger(ctx, deployment, "High Memory Risk")
		}
	}

}

// Handle trigger cooldown
// Key: trigger:cooldown:<deployment name>
// Value: timestamp
func (a *Aggregator) handleTrigger(ctx context.Context, c CostDeployment, reason string) {
	// define key
	key := fmt.Sprintf("trigger:cooldown:%s", c.Name)

	// check redis for the last timestamp
	// return a string and convert to int64
	lastTriggerStr, err := a.Client.Get(ctx, key).Result()

	// handle case if first time triggering
	if err == redis.Nil {
		a.executePush(ctx, key, c, reason)
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
	a.executePush(ctx, key, c, reason)
}

// push to queue and update timestamp
func (a *Aggregator) executePush(ctx context.Context, key string, c CostDeployment, reason string) {
	fmt.Printf("Pushing to queue for %s because: %s\n", c.Name, reason)

	// Push to queue
	// to be implemented

	// Update time
	a.Client.Set(ctx, key, time.Now().Unix(), 0)
}
