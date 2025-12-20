import json
from typing import Dict, Any
from state import AgentState
from llm.client import get_llm
from llm.prompts import get_optimiser_prompt

# this node updates thought_process and suggested_patch states
def reason_optimisation(state: AgentState) -> Dict[str, Any]:
    """
    Node: Reason
    Analyses metrics and generate a resource patch
    """
    print(f"Analysing deployment: {state['deployments']['name']}")

    deployment_data = state.get('deployments', {})
    dep_name = deployment_data.get('name', 'Unknown')
    # print(f"Analysing deployment: {dep_name}")

    # get llm and prompt - prepare data
    llm = get_llm()
    prompt = get_optimiser_prompt()
    chain = prompt | llm

    # extract prediction
    prediction_data = deployment_data.get("predicted_peak_24h", "No forecast available")

    # invoke llm
    # note: prediction might be None for pure Cost jobs, handle gracefully
    try:
       response = chain.invoke({
            "reason": state.get("reason", "Unknown"),
            "deployment_name": dep_name,
            "current_requests": deployment_data.get("current_requests", {}),
            "current_usage": deployment_data.get("current_usage", {}),
            "prediction": prediction_data
        })
    except Exception as e:
        print(f"LLM invocation failed: {e}")
        return {"thought_process": "LLM Error", "suggested_patch": {}}

    # parse output
    try: 
        decision = json.loads(response.content)

        if not validate_patch(decision.get("suggested_changes", {}), state):
            print("[WARNING] LLM output failed validation. Skipping this job.")
            return {"thought_process": "Validation failed", "suggested_patch": {}}

        # update state
        return {
            "thought_process": decision.get("thought_process", "No reasoning provided"),
            "suggested_patch": decision.get("suggested_changes", [])
        }
    except json.JSONDecodeError:
        print(f"LLM failed to output JSON: {response.content}")
        return {"thought_process": "Error: LLM output malformed", "suggested_patch": {}}

def parse_cpu_to_millicores(cpu_str: str) -> float:
    """Convert CPU string to millicores. Examples: '500m' -> 500, '1' -> 1000"""
    if cpu_str.endswith('m'):
        return float(cpu_str[:-1])
    return float(cpu_str) * 1000

def parse_memory_to_mb(mem_str: str) -> float:
    """Convert memory string to MB. Examples: '512Mi' -> 512, '1Gi' -> 1024"""
    mem_str = mem_str.upper()
    if mem_str.endswith('MI'):
        return float(mem_str[:-2])
    elif mem_str.endswith('GI'):
        return float(mem_str[:-2]) * 1024
    elif mem_str.endswith('M'):
        return float(mem_str[:-1])
    elif mem_str.endswith('G'):
        return float(mem_str[:-1]) * 1024
    return float(mem_str)

def validate_patch(patch: dict, job_data: dict) -> bool:
    """Check the LLM's proposed changes"""
    
    try:
        new_cpu_req = patch['resources']['requests']['cpu']
        new_mem_req = patch['resources']['requests']['memory']
        new_cpu_lim = patch['resources']['limits']['cpu']
        new_mem_lim = patch['resources']['limits']['memory']
        
        # Convert to numeric for comparison
        cpu_req_m = parse_cpu_to_millicores(new_cpu_req)
        mem_req_mb = parse_memory_to_mb(new_mem_req)
        cpu_lim_m = parse_cpu_to_millicores(new_cpu_lim)
        mem_lim_mb = parse_memory_to_mb(new_mem_lim)
        
        # Rule 1: Limits must be >= Requests
        if cpu_lim_m < cpu_req_m or mem_lim_mb < mem_req_mb:
            print("[ERROR] Limits are less than requests!")
            return False
        
        # Rule 2: Requests should not 10x increase (hallucination check)
        current_cpu_cores = job_data['deployments']['current_requests']['cpu_cores']
        current_cpu_m = current_cpu_cores * 1000
        
        if cpu_req_m > current_cpu_m * 10:
            print(f"[ERROR] Proposed CPU {cpu_req_m}m is 10x higher than current {current_cpu_m}m!")
            return False
        
        # Rule 3: For "High Waste" triggers, requests should DECREASE
        reason = job_data.get('reason', '')
        if 'Waste' in reason and cpu_req_m > current_cpu_m:
            print(f"[ERROR] High Waste trigger but CPU increased!")
            return False
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Patch validation failed: {e}")
        return False

