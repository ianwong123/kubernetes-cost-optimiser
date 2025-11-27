package internal

import (
	"context"
	"encoding/json"
	"strconv"

	"github.com/redis/go-redis/v9"
)

type AggregatorInterface interface {
	SaveCostPayload(p *CostPayload) error
	// SaveForecastPayloadp(p *ForecastPayload) error
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

// Marshal payload and save to redis
// Key - cost:latest:<time>
// Value - <payload>
func (a *Aggregator) SaveCostPayload(p *CostPayload) error {
	jsonData, err := json.Marshal(p)
	if err != nil {
		return err
	}

	key := "cost:latest:" + strconv.FormatInt(p.Timestamp.Unix(), 10)

	err = a.Client.Set(context.Background(), key, jsonData, 0).Err()
	if err != nil {
		return err
	}

	return nil
}

// func (a *Aggregator) SaveForecastPayload(p *ForecastPayload) error {
// 	jsonData, err := json.Marshal(p)
// 	if err != nil {
// 		return err
// 	}

// 	return nil
// }
