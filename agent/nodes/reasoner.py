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
    print(f"Analysing deployment: {dep_name}")

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

        # update state
        return {
            "thought_process": decision.get("thought_process", "No reasoning provided"),
            "suggested_patch": decision.get("suggested_changes", [])
        }
    except json.JSONDecodeError:
        print(f"LLM failed to output JSON: {response.content}")
        return {"thought_process": "Error: LLM output malformed", "suggested_patch": {}}

