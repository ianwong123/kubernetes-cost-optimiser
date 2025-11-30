# agent entry point - polls queue
import sys
import uuid
from utils.redis_client import get_redis_client
from queue_client import RedisQueueClient
from graph import app

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
                dep_info = job_data.get('deployments', {})
                dep_name = dep_info.get('name', 'Unknown')

                print(f"\nJob received: {dep_name}")
                print(f"Reason: {job_data.get('reason')}")
                #print(f"Deployment: {job_data.get('deployments', {}).get('name')}")

                # prepare initial state for langgraph
                # copy job data directly into state
                initial_state = job_data.copy()
                initial_state["job_id"] = str(uuid.uuid4())
                initial_state["memory_context"] = []
                initial_state["thought_process"] = ""
                initial_state["suggested_patch"] = {}
                initial_state["pr_url"] = None

                # run graph 
                print("Invoking LLM reasoner")
                result = app.invoke(initial_state)

                # print output
                print("Decision")
                print(f"Thought process: {result.get('thought_process')}")
                print(f"Suggested patch: {result.get('suggested_patch')}")
                print("======================================================")

            
        except KeyboardInterrupt:
            print("\nStopping Agent...")
            sys.exit(0)
        except Exception as e:
            print(f"Error: {e}")
            # In production,  might push this back to a dead-letter-queue?

if __name__ == "__main__":
    main()