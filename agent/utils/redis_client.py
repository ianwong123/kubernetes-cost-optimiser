import redis
import sys
import os

def get_redis_client():
    # creates a connection to redis
    # defaults to localhost for local testing via port forward
    redis_host = os.getenv("REDIS_SERVICE_ADDR", "localhost")
    redis_port = 6379
    
    if ":" in redis_host:
        redis_host, port_str = redis_host.split(":")
        redis_port = int(port_str)

    redis_pass = os.getenv("REDIS_SERVICE_PASS", "")

    try:
        client = redis.Redis(
            host=redis_host,
            port=redis_port,
            password=redis_pass if redis_pass else None,
            decode_responses=True
        )

        client.ping()
        print(f"Connected to redis client at {redis_host}:{redis_port}")
        return client

    except redis.ConnectionError as e:
        print(f"Failed to connect to redis {e}")
        sys.exit(1)