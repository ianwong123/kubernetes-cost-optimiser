# this file defines AgentState
from typing import TypedDict, Optional, Dict, List

class DeploymentInfo(TypedDict):
    name: str
    current_requests: Dict[str, float]
    current_usage: Dict[str, float]
    predicted_peak_24h: Optional[Dict[str, float]]

class ClusterInfo(TypedDict): 
    vm_count: float
    current_hourly_cost: float

# hold input, contexts, and output
class AgentState(TypedDict):
    job_id: str
    reason: str
    namespace: str
    deployments: DeploymentInfo
    cluster_info: ClusterInfo

    # memory
    # list similar past optimisations found in Redis
    memory_context: List[str]

    # update state reasoning from llm
    thought_process: str
    suggested_patch: str

    # outcome
    pr_url: Optional[str] 
    


