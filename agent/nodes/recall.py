from typign import Dict, Any
from state import AgentState
from utils.redis_client import get_redis_client
from memory.vectory_store import RedisVectorStore

def recall_memory(state: AgentState) -> Dict[str, Any]:
    """
    Node: Recall
    Query redis for similar past optimisation
    """

    print("Recalling past optimisaton from memory...")

    # Setup redis client
    client = get_redis_client()
    vector_store = RedisVectorStore(client)
