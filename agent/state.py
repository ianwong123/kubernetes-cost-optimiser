# this file defines AgentState
from typing import TypedDict, Optional, Dict, List

class DeploymentInfo:
    name: str
    current_requests: Dict[str, float]
    current_usage: Dict[str, float]
    predicted_peak_24h: Optional[Dict[str, float]]

class ClusterInfo: 
    vm_count: float
    current_hourly_cost: float

# hold input, contexts, and output
class AgentState:
    job_id: str
    reason: str
    namespace: str
    deployment_info: DeploymentInfo
    cluster_info: ClusterInfo

    # memory
    # list similar past optimisations found in Redis
    memory_context: List[str]

    # reasoning from llm
    thought_process: str
    suggested_patch: str

    # outcome
    pr_url: Optional[str] 
    


