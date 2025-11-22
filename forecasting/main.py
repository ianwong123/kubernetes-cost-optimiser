#!/usr/bin/env python3
"""
Kubernetes Resource Forecasting Service 
Runs as a persistent Service (Deployment)
Exposes metrics on HTTP port 8002 for Prometheus to scrape.
Forecasts the next 24 hours for multiple namespaces.

Architecture:
1. [Fetch]: Pulls 7 days of historical CPU/Memory usage from Prometheus.
2. [Compute]: Trains 'Prophet' time-series models for every deployment.
3. [Forecast]: Updates forecasts every N seconds.
4. [Visualise]: Prints detailed debug logs and visualization tables to stdout.
"""

import os
import sys
import pandas as pd
import requests
import re
import time
from datetime import datetime, timedelta
from prophet import Prophet
from prometheus_client import start_http_server, Gauge

#  Configuration 
# Run every 15 mins for testing
PROMETHEUS_READ_URL = "http://prometheus-server:80"
NAMESPACES = ["default", "monitoring", "kube-system", "databases", "argocd"] 
EXPORTER_PORT = 8002  
UPDATE_INTERVAL = 900

# Prometheus Metrics 
# Dimensions: Namespace, Deployment, Hours Ahead (1-24)
cpu_forecast_gauge = Gauge('k8s_cpu_forecast_cores', 'Predicted CPU', ['namespace', 'deployment', 'hours_ahead'])
mem_forecast_gauge = Gauge('k8s_memory_forecast_mb', 'Predicted Memory MB', ['namespace', 'deployment', 'hours_ahead'])
last_run_gauge = Gauge('k8s_forecast_last_run_timestamp', 'Timestamp of last forecast update')

# Aggregated Metrics (Total per namespace)
total_cpu_forecast_gauge = Gauge('k8s_total_cpu_forecast_cores', 'Total predicted CPU for namespace', ['namespace', 'hours_ahead'])
total_mem_forecast_gauge = Gauge('k8s_total_memory_forecast_mb', 'Total predicted memory for namespace', ['namespace', 'hours_ahead'])

# Helper: Workload Name Extractor 
def extract_workload_name(pod_name):
    # Pattern 1: Standard Deployment (name-replicaset-pod)
    match_dep = re.search(r"^(.*)-[a-z0-9]{3,10}-[a-z0-9]{5}$", pod_name)
    if match_dep: return match_dep.group(1)
    # Pattern 2: StatefulSet (name-number)
    match_ss = re.search(r"^(.*)-\d+$", pod_name)
    if match_ss: return match_ss.group(1)
    return pod_name

# 1. Data Fetching Layer 
def get_deployment_metrics(namespace, hours=168, metric_type="cpu"):
    print(f"[DEBUG] Fetching {metric_type.upper()} history for namespace '{namespace}' (last {hours}h)...")
    
    if metric_type == "cpu":
        query = f'sum by (pod) (rate(container_cpu_usage_seconds_total{{namespace="{namespace}", container!="POD", container!=""}}[5m]))'
    else:
        query = f'sum by (pod) (container_memory_working_set_bytes{{namespace="{namespace}", container!="POD", container!=""}})'

    end_time = datetime.now()
    start_time = end_time - timedelta(hours=hours)
    
    try:
        # Requesting Data
        response = requests.get(f"{PROMETHEUS_READ_URL}/api/v1/query_range", params={
            'query': query, 'start': start_time.timestamp(), 'end': end_time.timestamp(), 'step': '15m' 
        }, timeout=10)
        
        if response.status_code != 200:
            print(f"[ERROR] HTTP {response.status_code}: {response.text}")
            return {}
            
        data = response.json()
        if data['status'] != 'success':
            print(f"[ERROR] Prometheus Error: {data.get('error')}")
            return {}
            
        results = data['data']['result']
        print(f"[DEBUG] Received {len(results)} raw pod timeseries for namespace {namespace}.")
        
        if not results:
            print(f"[WARN] No metrics found for namespace {namespace}")
            return {}

        # Processing & Grouping by Deployment
        raw_pod_data = {}
        for result in results:
            pod_name = result['metric'].get('pod', 'unknown')
            dep_name = extract_workload_name(pod_name)
            
            values = [float(v) for _, v in result['values']]
            timestamps = [datetime.fromtimestamp(float(t)) for t, _ in result['values']]
            
            if metric_type == "memory": values = [v / (1024**2) for v in values]
            
            if values:
                df = pd.DataFrame({'ds': timestamps, 'y': values})
                if dep_name not in raw_pod_data: raw_pod_data[dep_name] = []
                raw_pod_data[dep_name].append(df)

        # Aggregating Pods -> Deployments
        deployments_data = {}
        for dep_name, dfs in raw_pod_data.items():
            grouped_df = pd.concat(dfs).groupby('ds')['y'].sum().reset_index().sort_values('ds')
            deployments_data[dep_name] = grouped_df
            # print(f"[DEBUG]   -> {namespace}/{dep_name}: {len(grouped_df)} data points")

        return deployments_data

    except Exception as e:
        print(f"[ERROR] Exception during fetch for namespace {namespace}: {e}")
        return {}

# 2. Forecasting Layer 
def generate_forecasts(data_map):
    results = {}
    if not data_map: return results
    
    print(f"[INFO] Training models for {len(data_map)} deployments...")
    
    for name, df in data_map.items():
        if len(df) < 12:
            # print(f"[WARN] Skipping {name}: Insufficient data ({len(df)} points)")
            continue
            
        try:
            with open(os.devnull, 'w') as devnull:
                sys.stdout = devnull
                m = Prophet(changepoint_prior_scale=0.05, daily_seasonality=False, weekly_seasonality=False)
                m.fit(df)
                future = m.make_future_dataframe(periods=24, freq='h')
                forecast = m.predict(future)
                sys.stdout = sys.__stdout__

            results[name] = {'forecast': forecast, 'history': df}
        except Exception as e:
            sys.stdout = sys.__stdout__
            print(f"[ERROR] Training failed for {name}: {e}")
            
    return results

# 3. Visualisation Layer 
def display_terminal_summary(all_cpu_results, all_mem_results):
    print("\n" + "="*120)
    print(f"CLUSTER FORECAST SUMMARY: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*120)
    
    # 1. Calculate Global Cluster Totals
    g_cpu_h, g_cpu_n, g_cpu_p = 0.0, 0.0, 0.0
    g_mem_h, g_mem_n, g_mem_p = 0.0, 0.0, 0.0
    
    # Helper to sum up a nested dict of results
    def sum_results(results_dict):
        h, n, p = 0.0, 0.0, 0.0
        for ns in results_dict.values():
            for app_data in ns.values():
                h += app_data['history']['y'].mean()
                n += app_data['history']['y'].iloc[-1]
                p += app_data['forecast'].tail(24)['yhat'].mean()
        return h, n, p

    g_cpu_h, g_cpu_n, g_cpu_p = sum_results(all_cpu_results)
    g_mem_h, g_mem_n, g_mem_p = sum_results(all_mem_results)

    print(f" GLOBAL TOTALS:")
    print(f"   CPU:    Hist: {g_cpu_h:6.2f} Cores | Now: {g_cpu_n:6.2f} Cores | Pred: {g_cpu_p:6.2f} Cores")
    print(f"   MEMORY: Hist: {g_mem_h:6.2f} MB    | Now: {g_mem_n:6.2f} MB    | Pred: {g_mem_p:6.2f} MB")
    print("="*120)
    
    # 2. Namespace Breakdown
    for namespace in NAMESPACES:
        cpu_results = all_cpu_results.get(namespace, {})
        mem_results = all_mem_results.get(namespace, {})
        
        if not cpu_results and not mem_results:
            continue
            
        ns_cpu_h, ns_cpu_n, ns_cpu_p = 0.0, 0.0, 0.0
        ns_mem_h, ns_mem_n, ns_mem_p = 0.0, 0.0, 0.0
        
        # Sum per namespace
        for d in cpu_results.values():
            ns_cpu_h += d['history']['y'].mean()
            ns_cpu_n += d['history']['y'].iloc[-1]
            ns_cpu_p += d['forecast'].tail(24)['yhat'].mean()
            
        for d in mem_results.values():
            ns_mem_h += d['history']['y'].mean()
            ns_mem_n += d['history']['y'].iloc[-1]
            ns_mem_p += d['forecast'].tail(24)['yhat'].mean()
        
        print(f" NAMESPACE: {namespace}")
        print(f"   CPU:    Hist: {ns_cpu_h:6.2f} Cores | Now: {ns_cpu_n:6.2f} Cores | Pred: {ns_cpu_p:6.2f} Cores")
        print(f"   MEMORY: Hist: {ns_mem_h:6.2f} MB    | Now: {ns_mem_n:6.2f} MB    | Pred: {ns_mem_p:6.2f} MB")
        print("-" * 120)

#  4. Metrics Update Layer 
def update_prometheus_metrics(all_cpu_results, all_mem_results):
    print("[INFO] Updating Prometheus Gauges...")
    now = datetime.now()
    total_deployments = 0
    
    # Process each namespace
    for namespace in NAMESPACES:
        cpu_results = all_cpu_results.get(namespace, {})
        mem_results = all_mem_results.get(namespace, {})
        
        # Track totals per hour for this namespace
        # Dictionary key: hour (1-24), value: sum
        ns_cpu_hourly_sum = {h: 0.0 for h in range(1, 25)}
        ns_mem_hourly_sum = {h: 0.0 for h in range(1, 25)}
        
        # 1. Update Deployment CPU
        for app, data in cpu_results.items():
            future_df = data['forecast'][data['forecast']['ds'] > now].head(24)
            for _, row in future_df.iterrows():
                h = int((row['ds'] - now).total_seconds() / 3600) + 1
                if 1 <= h <= 24:
                    val = max(0, row['yhat'])
                    cpu_forecast_gauge.labels(namespace=namespace, deployment=app, hours_ahead=str(h)).set(val)
                    ns_cpu_hourly_sum[h] += val
            
        # 2. Update Deployment Memory
        for app, data in mem_results.items():
            future_df = data['forecast'][data['forecast']['ds'] > now].head(24)
            for _, row in future_df.iterrows():
                h = int((row['ds'] - now).total_seconds() / 3600) + 1
                if 1 <= h <= 24:
                    val = max(0, row['yhat'])
                    mem_forecast_gauge.labels(namespace=namespace, deployment=app, hours_ahead=str(h)).set(val)
                    ns_mem_hourly_sum[h] += val

        # 3. Update Namespace Totals
        for h in range(1, 25):
            total_cpu_forecast_gauge.labels(namespace=namespace, hours_ahead=str(h)).set(ns_cpu_hourly_sum[h])
            total_mem_forecast_gauge.labels(namespace=namespace, hours_ahead=str(h)).set(ns_mem_hourly_sum[h])
            
        # Count unique apps in this namespace
        unique_apps = set(cpu_results.keys()) | set(mem_results.keys())
        total_deployments += len(unique_apps)
        
        if unique_apps:
            avg_cpu_future = sum(ns_cpu_hourly_sum.values()) / 24
            avg_mem_future = sum(ns_mem_hourly_sum.values()) / 24
            print(f"[INFO]    {namespace}: {len(unique_apps)} apps | Avg Future Load: {avg_cpu_future:.2f} Cores, {avg_mem_future:.2f} MB")
    
    last_run_gauge.set(time.time())
    print(f"[INFO] Successfully updated metrics for {total_deployments} unique deployments.")

# Main Loop 
def update_loop():
    print(f"\nSTARTING FORECAST RUN: {datetime.now()}")
    
    all_cpu_results = {}
    all_mem_results = {}
    
    for namespace in NAMESPACES:
        # Fetch
        cpu_data = get_deployment_metrics(namespace, hours=168, metric_type="cpu")
        mem_data = get_deployment_metrics(namespace, hours=168, metric_type="memory")
        
        # Forecast
        all_cpu_results[namespace] = generate_forecasts(cpu_data)
        all_mem_results[namespace] = generate_forecasts(mem_data)
    
    # Update Metrics
    update_prometheus_metrics(all_cpu_results, all_mem_results)
    
    # Visualize
    display_terminal_summary(all_cpu_results, all_mem_results)
    
    print(f"[INFO] Run complete. Sleeping for {UPDATE_INTERVAL}s...")

def main():
    print(f"Starting Forecasting Service on port {EXPORTER_PORT}...")
    print(f"Monitoring namespaces: {NAMESPACES}")
    
    try:
        start_http_server(EXPORTER_PORT)
    except Exception as e:
        print(f"[FATAL] Failed to start HTTP server: {e}")
        sys.exit(1)
    
    # Run immediately first time
    update_loop()
    
    while True:
        time.sleep(UPDATE_INTERVAL)
        update_loop()

if __name__ == "__main__":
    main()