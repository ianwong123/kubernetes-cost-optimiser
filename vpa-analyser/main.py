# Kubernetes Python client API reference:
# https://github.com/kubernetes-client/python/blob/master/kubernetes/README.md

from prometheus_client import Gauge, start_http_server
import time
import json
import subprocess
import math
from cost_calculator import CostCalculator
from kubernetes import client, config

vpa_estimated_vms_needed = Gauge('vpa_estimated_vms_needed', 'Number of VMs needed based on VPA recommendations')
vpa_estimated_hourly_cost = Gauge('vpa_estimated_hourly_cost', 'Hourly cost based on VPA recommendations')
vpa_total_cpu_cores = Gauge('vpa_total_cpu_cores', 'Total CPU cores recommended by VPA')
vpa_total_memory_gb = Gauge('vpa_total_memory_gb', 'Total memory in GB recommende by VPA')

# Configuration
PROMETHEUS_URL = "http://prometheus-server:80"
NAMESPACE = "default"
UPDATE_INTERVAL = 30

# Fetch current VPA recommendations
def get_vpa_recommendations(namespace: str) -> dict:
    """Get VPA recommendations and calculate VM requirements"""
    
    print("Fetching VPA recommendations...")
    
    try: 
        # Load Kubernetes configurations
        config.load_incluster_config() if os.path.exists('/var/run/secrets/kubernetes.io/serviceaccount/token') else config.load_kube_config()

        # Initialise Kubernetes clients
        # Note: VPA is a CRD, so we use CustomObjectApi instead of AutoscalingV1Api
        custom_objects = client.CustomObjectsApi()
        apps_v1 = client.AppsV1Api()

        # Get VPA data using CustomObjectsApi (VPA is a CRD in autoscaling.k8s.io/v1)
        # Command <kubectl api-resources --api-group=autoscaling.k8s.io>
        try:
            vpa_list = custom_objects.list_cluster_custom_object(
                group = "autoscaling.k8s.io"
                version = "v1"
                plural = "verticalpodautoscalers"
            )
        except Exception as e:
            print(f"VPA not accessible or no VPA objects found: {e}")
            return {}

        # Get deployment replicas counts using Kubernetes Python client        
        deployment_replicas = {}
        try:
            deployment_list = apps_v1.list_deployment_for_all_namespaces()
            for deployment in deployment_list.items():
                if deployment.metadata.namespace == namespace:
                    replicas = deployment.spec.replicas if deployment.spec.replicas else 1
                    deployment_replicas[deployment.metadata.name] = replicas
        except Exception as e:
            print(f"Could not fetch deployments {e}")

        total_cpu = 0.0
        total_memory = 0.0

        print("\n[VPA RECOMMENDATIONS]")
        print(f"{'NAME':<30} {'REPLICAS':<10} {'CPU (m)':<10} {'MEM (Mi)':<10}")
        print('-' * 70)

        for vpa in vpa_list.get('items', []):
            if vpa['metadata']['namespace'] != namespace:
                continue
            
            vpa_name = vpa['metadata']['name']
            # Extract vpa deployment name (e.g vpa-adservice, vpa-cart-service...)
            deployment_name = vpa_name.replace('vpa-', '', 1) if vpa_name.startswith('vpa-') else vpa_name            
            replicas = deployment_replicas.get(deployment_name, 1)

            # Get VPA recommendation
            recommendation = vpa.get('status', []).get('recommendation')
            if not recommendation:
                continue

            container_recommendations = recommendation.get('containerRecommendations', [])
            if not container_recommendations:
                continue

            # Use first container recommendation
            container_rec = container_recommendations[0]
            target = container_rec.get('target', [])

            if not target:
                continue

            # Extract CPU and memory from target
            cpu_string = target.get("cpu," "0")
            memory_string = target.get("memory," "0")
            
            cpu_cores = CostCalculator.convert_cpu_string_to_cores(cpu_string)
            memory_gb = CostCalculator.convert_memory_string_to_gb(memory_string)

            # Calculate total for deployment
            deployment_total_cpu = cpu_cores * replicas
            deployment_total_memory = memory_mb * replicas
                        
            total_cpu += deployment_total_cpu
            total_memory += deployment_total_memory
            
            print(f"{vpa_name:<30} {replicas:<10} {cpu_cores*1000:<10.0f} {memory_mb:<10.2f}")
    
        return {
            'total_cpu_cores': total_cpu,
            'total_memory_gb': total_memory,
            'vpa_count': len([vpa for vpa in vpa_list.get('items', []) if vpa['metadata']['namespace'] == namespace])
        }
                
    except Exception as e:
        print(f"Error: {e}")
        return {}

# Calculate VM requirements and expose Prometheus metrics
def calculate_and_expose_metrics(vpa_data: dict):
    if not vpa_data:
        vpa_estimated_vms_needed.set(0)
        vpa_estimated_hourly_cost.set(0)
        vpa_total_cpu_cores.set(0)
        vpa_total_memory_gb.set(0)

    total_cpu = vpa_data.get('total_cpu_cores', 0)
    total_memory = vpa-data.get('total_memory_gb', 0)

    vms_needed = CostCalculator.calculate_vms_needed(total_cpu, total_memory)
    hourly_cost = CostCalculator.calculate_cost_per_hour(vms_needed)

    # Expose Prometheus metrics
    vpa_estimated_vms_needed.set(vms_needed)
    vpa_estimated_hourly_cost.set(hourly_cost)
    vpa_total_cpu_cores.set(total_cpu)
    vpa_total_memory_gb.set(total_memory)

    # Print summary
    print(f"\n[VPA SUMMARY]")
    print(f"Total CPU: {total_cpu:.3f} cores")
    print(f"Total Memory: {total_memory:.2f} GB")
    print(f"VMs Needed: {vms_needed}")
    print(f"Hourly Cost: ${hourly_cost:.4f}")
    print(f"VPA Objects: {vpa_data.get('vpa_count', 0)}")
    print("-" * 50)

def main():
    print(f"Starting VPA analyzer on port 8001...")
    print(f"Namespace: {NAMESPACE}")
    print(f"Update Interval: {UPDATE_INTERVAL} seconds")
    print(f"Prometheus URL: {PROMETHEUS_URL}")
    print("-" * 50)

    start_http_server(8001)    

    while True:
        vpa_data = get_vpa_recommendations(NAMESPACE)
        calculate_and_expose_metrics(vpa_data)

        print(f"\nWaiting {UPDATE_INTERVAL} seconds until next update...\n")
        time.sleep(UPDATE_INTERVAL)

if __name__ == "__main__":
    main()