class RedisVectorStore:
    def __init__(self, redis_client: Redis):
        self.client = redis_client