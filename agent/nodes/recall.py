from typign import Dict, Any
from state import AgentState
from utils.redis_client import get_redis_client
from memory.vector_store import RedisVectorStore

def recall_memory(state: AgentState) -> Dict[str, Any]:
    """
    Node: Recall
    Query redis for similar past optimisation
    """

    print("Recalling past optimisaton from memory...")

    # Setup redis client
    client = get_redis_client()
    vector_store = RedisVectorStore(client)

    # setup query
    dep_name = state['deployments']['name']
    reason = state['reason']
    query = f"Deployments: {dep_name}, Reason: {reason}"

    # perform search, update state memory_context
    try:
        memories = vector_store.search_similar(query, k=3)
        print(f"Found {len(memories)} relevant past optimisations")
        return {"memory_context": memories}
    except Exception as e:
        print(f"Error lookup failed: {e}")
        return {"memory_context": []}
