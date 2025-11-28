package queue

import "context"

type QueueClient interface {
	PublishJob(ctx context.Context, queueName string, payload interface{}) error
}
