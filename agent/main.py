# agent entry point - polls queue
import sys
from utils.redis_client import get_redis_client
from queue_client import RedisQueueClient

def main():
    print("Starting Agent optimiser...")
    
    # Setup Connection
    redis_conn = get_redis_client()
    queue: QueuePoller = RedisQueueClient(redis_conn)

    print(f"Polling queue: {queue.queue_name}")

    while True:
        try:
            # poll for job (blocks until arrival)
            job_data = queue.poll()
            
            if job_data:
                print("\nJob received")
                print(f"Reason: {job_data.get('reason')}")
                print(f"Deployment: {job_data.get('deployments', {}).get('name')}")
            
        except KeyboardInterrupt:
            print("\nStopping Agent...")
            sys.exit(0)
        except Exception as e:
            print(f"Error error: {e}")
            # In production,  might push this back to a dead-letter-queue?

if __name__ == "__main__":
    main()