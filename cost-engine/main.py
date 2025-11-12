#!/usr/bin/env python3
"""
Cost engine - Calculates VM cost from current Kuberentes resource requests  
Exposes metrics to Prometheus for visualisation in Grafana
"""
from prometheus_client import Gauge, start_http_server
import time
import requests
from cost_calculator import CostCalculator

# Prometheus metrics
estimated_cost = Gauge('kubernetes_estimated_hourly_cost', 'Estimated hourly cost in USD')
estimated_vms = Gauge('kubernetes_estimated_vms_needed', 'Number of VMs needed')
cpu_vms_needed = Gauge('kubernetes_cpu_vms_needed', 'VMs needed for CPU requests')
memory_vms_needed = Gauge('kubernetes_memory_vms_needed', 'VMs needed for memory requests')
cost_by_namespace = Gauge('kubernetes_cost_by_namespace', 'Cost by namespace', ['namespace'])

# Configuration 
PROMETHEUS_URL = "http://prometheus-server:80"

# Get all cpu requests from all pods across all namespaces
def get_total_cpu_requests():
    query = 'sum(kube_pod_container_resource_requests{resource="cpu"})'
    response = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={'query': query})
    result = response.json()
    print(result)
    if result['status'] == 'success' and result['data']['result']:
        return float(result['data']['result'][0]['value'][1])
    return 0.0

# Get all memory requests from all pods across all namespaces
def get_total_memory_requests():
    query = 'sum(kube_pod_container_resource_requests{resource="memory"}))'
    response = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={'query': query})
    result = response.json()
    print(result)
    if result['status'] == 'success' and result['data']['result']:
        bytes_value = float(result['data']['result'][0]['value'][1])
        return bytes_value / (1024 ** 3)
    return 0.0

# Calculate and expose overall cost metrics
def calcualte_overall_cost():
    try:
        total_cpu = get_total_cpu_requests()
        total_mem = get_total_memory_requests()

        # Use shared calculator
        vms_needed = CostCalculator.calculate_vms_needed(total_cpu, total_mem)
        cost = CostCalculator.calculate_cost_per_hour(vms_needed)

        # Calculate individual resource requirements
        cpu_vms = CostCalculator.calculate_vms_needed(total_cpu, 0)
        mem_vms = CostCalculator.calculate_vms_needed(0, total_mem)

        # Set Prometheus metrics
        estimated_cost.set(cost)
        estimated_vms.set(vms_needed)
        cpu_vms_needed.set(cpu_vms)
        memory_vms_needed.set(mem_vms)

        print(f"CPU: {total_cpu:.2f} cores -> {cpu_vms} VMs")
        print(f"Memory: {total_mem:.2f} GB -> {mem_vms} VMs")
        print(f"Total VMs needed: {vms_needed}, Cost: {cost:.4f}/hour")

    except Exception as e:
        print(f"Error calculating overall cost: {e}")
        
# Calculate and expose cost metrics by namespace
def calculate_cost_by_namespace():
    try:
        query_cpu = 'sum(kube_pod_container_resource_requests{resource="cpu"}) by (namespace)'
        query_mem = 'sum(kube_pod_container_resource_requests{resource="memory"}) by (namespace)'

        response_cpu = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={'query': query_cpu})
        response_mem = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={'query': query_mem})

        cpu_data = response_cpu.json()['data']['result']
        mem_data = response_mem.json()['data']['result']

        # Lookup for memory in namespace
        mem_lookup = {entry['metric']['namespace']: CostCalculator.convert_memory_to_gb(float(entry['value'][1]))
        for entry in mem_data}

        for cpu_entry in cpu_data:
            namespace = cpu_entry['metric']['namespace']
            cpu_cores = float(cpu_entry['value'][1])
            memory_gb = mem_lookup.get(namespace, 0)

            vms_needed = CostCalculator.calculate_vms_needed(cpu_cores, memory_gb)
            cost = CostCalculator.calculate_cost_per_hour(vms_needed)

            cost_by_namespace.labels(namespace=namespace).set(cost)
            print(f"{namespace}: {cpu_cores:.2f} CPU + {memory_gb:.2f} GB -> {vms_needed} VMs -> ${cost:.4f}/hour")

    except Exception as e:
        print(f"Error calculating namesapce cost: {e}")
        
def main():
    print("Starting cost engine on port 8000...")
    start_http_server(8000)
    get_total_cpu_requests()

    while True:
        calcualte_overall_cost()
        calculate_cost_by_namespace()
        print("-" * 50)
        time.sleep(15)

if __name__ == "__main__":
    main()

