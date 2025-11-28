package queue

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/redis/go-redis/v9"
)

type RedisQueue struct {
	Client *redis.Client
}

func NewRedisQueue(client *redis.Client) *RedisQueue {
	return &RedisQueue{Client: client}
}

// Implements PublishJob
func (r *RedisQueue) PublishJob(ctx context.Context, queueName string, payload interface{}) error {
	// payload is of type CostDeployment struct -> convert to Json string
	jsonData, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("failed to marshal payload: %w", err)
	}

	// Push to redis queue
	err = r.Client.LPush(ctx, queueName, jsonData).Err()
	if err != nil {
		return fmt.Errorf("failed to push to redis queue: %w", err)
	}

	return nil
}
