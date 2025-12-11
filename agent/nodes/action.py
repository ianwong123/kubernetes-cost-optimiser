from typing import Any, Dict
from state import AgentState
from tools.scm_client import SCMClient, GitHubClient

def execute_pr(state: AgentState) -> Dict[str, Any]:
    """
    Node: Action
    Opens a PR with proposed optimisations
    """

    # Inject client
    scm_client: SCMClient = None

    try:
        scm_client = GitHubClient()
    except Exception as e:
        print(f"SCM Client initialisation failed (Skipping PR): {e}")
        return ({"pr_url": None})

    # extract data from state
    job_id = state["job_id"]
    dep_name = state["deployments"]["name"]
    patch = state["suggested_patch"]
    reasoning = state["thought_process"]

    # if empty patch, skip PR
    if not patch:
        print("No patch generated, skipping PR...")
        return({"pr_url": None})

    # create PR
    pr_url = scm_client.create_pr(job_id, dep_name, patch, reasoning)

    if pr_url:
        print(f"PR created: {pr_url}")

    return {"pr_url": pr_url}

    