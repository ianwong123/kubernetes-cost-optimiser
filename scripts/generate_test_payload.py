import requests
import json
import re
import math
from datetime import datetime, timezone

PROM_URL = "http://prometheus.local.io"
NAMESPACE = "default"

def query_prom(query):
    try:
        resp = requests.get(f"{PROM_URL}/api/v1/query", params={"query": query})
        resp.raise_for_status()
        return resp.json()["data"]["result"]
    except Exception:
        return []

def extract_deployment_name(pod_name):
    match = re.search(r"^(.*)-[a-z0-9]+-[a-z0-9]+$", pod_name)
    return match.group(1) if match else pod_name

def get_deployment_metrics():
    queries = {
        ("current_requests", "cpu_cores"): f'sum(kube_pod_container_resource_requests{{resource="cpu", namespace="{NAMESPACE}"}}) by (pod)',
        ("current_requests", "memory_mb"): f'sum(kube_pod_container_resource_requests{{resource="memory", namespace="{NAMESPACE}"}}) by (pod)',
        ("current_usage", "cpu_cores"): f'sum(rate(container_cpu_usage_seconds_total{{namespace="{NAMESPACE}", container!=""}}[5m])) by (pod)',
        ("current_usage", "memory_mb"): f'sum(container_memory_working_set_bytes{{namespace="{NAMESPACE}", container!=""}}) by (pod)'
    }

    dep_data = {}

    for (category, metric_key), q in queries.items():
        results = query_prom(q)
        for r in results:
            pod = r["metric"].get("pod")
            if not pod: continue
            
            dep_name = extract_deployment_name(pod)
            val = float(r["value"][1])

            if dep_name not in dep_data:
                dep_data[dep_name] = {
                    "name": dep_name, 
                    "current_requests": {"cpu_cores": 0.0, "memory_mb": 0.0}, 
                    "current_usage": {"cpu_cores": 0.0, "memory_mb": 0.0}
                }
            
            dep_data[dep_name][category][metric_key] += val

    for dep in dep_data.values():
        for cat in ["current_requests", "current_usage"]:
            cpu = dep[cat]["cpu_cores"]
            dep[cat]["cpu_cores"] = max(0.1, math.ceil(cpu * 10) / 10) if cpu > 0 else 0.0
            
            mem_mb = dep[cat]["memory_mb"] / (1024 * 1024)
            dep[cat]["memory_mb"] = int(round(mem_mb))

    return list(dep_data.values())

def generate_payload():
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "namespace": NAMESPACE,
        "cluster_info": {"vm_count": 5, "current_hourly_cost": 0.20},
        "deployments": get_deployment_metrics()
    }
    print(json.dumps(payload, indent=2))

if __name__ == "__main__":
    generate_payload()