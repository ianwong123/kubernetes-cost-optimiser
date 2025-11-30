import json
from abc import ABC, abstractmethod 
from typing import Optional, Dict, Any
from redis import Redis

class QueuePoller(ABC):
    @abstractmethod
    def poll(self, timeout: int=0) -> Optional[Dict[str, Any]]:
        pass

class RedisQueueClient(QueuePoller):
    def __init__(self, client: Redis, queue_name: str = "queue:agent:jobs"):
        self.client = client
        self.queue_name = queue_name

    def poll(self, timeout: int=0) -> Optional[Dict[str, Any]]:
        # blocking poll for a job from queue
        # returns parsed dictionary or none if timeout/error
        try:
            result = self.client.brpop(self.queue_name, timeout=timeout)
            if result:
                _, row_data = result
                return json.loads(row_data)
            return None
        except Exception as e:
            print(f"Queue poll error {e}")
            return None