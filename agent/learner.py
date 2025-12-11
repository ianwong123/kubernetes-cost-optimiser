import uvicorn
from fastapi import FastAPI, Request
from typing import Any, Dict
from utils.redis_client import get_redis_client
from memory.vector_store import RedisVectorStore

app = FastAPI()
redis_client = get_redis_client()
memory = RedisVectorStore(redis_client)

@app.post("/webhook")
async def handle_github_webhook(request: Request):
    """
    Listen for pr request events from github
    If a pr is closed and merged, it stores the reasoning in redis memory
    """

    payload = await request.json()

    # filter pr events
    if "pull_request" not in payload:
        return {"status": "ignored", "message": "not a pr event"}

    action = payload.get("action")
    pr = payload.get("pull_request")
    merged = pr.get("merged", False)

    if action == "closed" and merged:
        return process_merged_pr(pr)

    return {"status": "ignored"}

def process_merged_pr(pr: Dict[str, Any]) -> Dict[str, str]: 
    """Extract reasoning from merged pr and save it to memory"""
    
    # title - optimise-<some service>-<job id>
    title = pr.get("title")

    # body contains the reasoning
    body = pr.get("body")
    print(f"PR merged: {title}")

    # extract lesson and outcome from payload
    scenario = f"{title} - {body}"
    outcome = "Success (Merged)"

    # commit to memory
    memory.add_memory(scenario, outcome)
    print("Memory updated. Knowledge added to Vector Store")
    return {"status": "learned"}

if __name__ == "__main__":
    print("Learner listening on port 8010...")
    uvicorn.run(app, host="0.0.0.0", port=8010)