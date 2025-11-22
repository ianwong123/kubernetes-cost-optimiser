#!/usr/bin/env python3
"""
Kubernetes Resource Forecasting Service 
Runs as a persistent Service (Deployment)
Deploy as a batch operation can be decided later on if it requires. Simplicity for now 
Exposes metrics on HTTP port 8002 for Prometheus to scrape
Forecast the next 24 hours 

Architecture:
1. [Fetch]: Pulls 7 days of historical CPU/Memory usage from Prometheus
2. [Compute]: Trains 'Prophet' time-series models for every deployment
3. [Forecast]: Updates forecasts every 4 hours
4. [Visualise]: Prints detailed debug logs and visualization tables to stdout.
5. [Payload]: (DISABLED) Constructs a JSON Snapshot 
6. [Push]: (DISABLED) POSTs the snapshot to the central Metric Hub (API Gateway Aggregator)
"""

import pandas as pd
import requests
import sys
import os
import re
import time
from datetime import datetime, timedelta
from prophet import Prophet
from prometheus_client import start_http_server, Gauge

# Configuration 
PROMETHEUS_READ_URL = os.getenv("PROMETHEUS_URL", "http://prometheus.local.io")
NAMESPACE = "default"
EXPORTER_PORT = 8002  
UPDATE_INTERVAL = 14400 

#  Prometheus Metrics 
cpu_forecast_gauge = Gauge('k8s_cpu_forecast_cores', 'Predicted CPU', ['deployment', 'hours_ahead'])
mem_forecast_gauge = Gauge('k8s_memory_forecast_mb', 'Predicted Memory MB', ['deployment', 'hours_ahead'])
last_run_gauge = Gauge('k8s_forecast_last_run_timestamp', 'Timestamp of last forecast update')

# Helper: Workload Name Extractor 
def extract_workload_name(pod_name):
    # Pattern 1: Standard Deployment (name-replicaset-pod)
    match_dep = re.search(r"^(.*)-[a-z0-9]{3,10}-[a-z0-9]{5}$", pod_name)
    if match_dep: return match_dep.group(1)
    # Pattern 2: StatefulSet (name-number)
    match_ss = re.search(r"^(.*)-\d+$", pod_name)
    if match_ss: return match_ss.group(1)
    return pod_name

# Data Fetching Layer 
def get_deployment_metrics(namespace, hours=168, metric_type="cpu"):
    print(f"[DEBUG] Fetching {metric_type.upper()} history (last {hours}h)...")
    
    if metric_type == "cpu":
        query = f'sum by (pod) (rate(container_cpu_usage_seconds_total{{namespace="{namespace}", container!="POD", container!=""}}[5m]))'
    else:
        query = f'sum by (pod) (container_memory_working_set_bytes{{namespace="{namespace}", container!="POD", container!=""}})'

    end_time = datetime.now()
    start_time = end_time - timedelta(hours=hours)
    
    try:
        # Requesting Data
        print(f"[DEBUG] GET {PROMETHEUS_READ_URL}/api/v1/query_range")
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
        print(f"[DEBUG] Received {len(results)} raw pod timeseries.")
        
        if not results:
            print(f"[WARN] No metrics found for query: {query}")
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
            print(f"[DEBUG]   -> {dep_name}: {len(grouped_df)} data points")

        return deployments_data

    except Exception as e:
        print(f"[ERROR] Exception during fetch: {e}")
        return {}

# Forecasting Layer 
def generate_forecasts(data_map):
    results = {}
    print(f"[INFO] Training models for {len(data_map)} deployments...")
    
    for name, df in data_map.items():
        if len(df) < 12:
            print(f"[WARN] Skipping {name}: Insufficient data ({len(df)} points)")
            continue
            
        try:
            # print(f"[DEBUG] Training Prophet for {name}...") # Uncomment for very verbose logs
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

# Visualisation Layer 
def display_terminal_summary(cpu_results, mem_results):
    all_apps = set(cpu_results.keys()) | set(mem_results.keys())
    if not all_apps: return

    # Calculate Totals
    t_cpu_h, t_cpu_n, t_cpu_p = 0.0, 0.0, 0.0
    t_mem_h, t_mem_n, t_mem_p = 0.0, 0.0, 0.0

    for app in all_apps:
        if app in cpu_results:
            t_cpu_h += cpu_results[app]['history']['y'].mean()
            t_cpu_n += cpu_results[app]['history']['y'].iloc[-1]
            t_cpu_p += cpu_results[app]['forecast'].tail(24)['yhat'].mean()
        if app in mem_results:
            t_mem_h += mem_results[app]['history']['y'].mean()
            t_mem_n += mem_results[app]['history']['y'].iloc[-1]
            t_mem_p += mem_results[app]['forecast'].tail(24)['yhat'].mean()

    print("\n" + "="*113)
    print(f"CLUSTER TOTALS (All {len(all_apps)} Deployments)")
    print("-" * 113)
    print(f" TOTAL CPU:    Hist: {t_cpu_h:6.2f} Cores | Now: {t_cpu_n:6.2f} Cores | Pred: {t_cpu_p:6.2f} Cores")
    print(f" TOTAL MEMORY: Hist: {t_mem_h:6.2f} MB    | Now: {t_mem_n:6.2f} MB    | Pred: {t_mem_p:6.2f} MB")
    print("="*113)

    print(f"| {'DEPLOYMENT':<25} | {'CPU (Cores)':^23} | {'MEMORY (MB)':^23} | {'ANALYSIS':^23} |")
    print("|" + "-"*27 + "|" + "-"*25 + "|" + "-"*25 + "|" + "-"*25 + "|")
    print(f"| {'(Name)':<25} | {'Hist':>6} {'Now':>7} {'Pred':>7} | {'Hist':>6} {'Now':>7} {'Pred':>7} | {'Trend':>9} {'% Diff':>11} |")
    print("="*113)
    
    for app in sorted(all_apps):
        cpu_h, cpu_n, cpu_p = 0.0, 0.0, 0.0
        mem_h, mem_n, mem_p = 0.0, 0.0, 0.0
        
        if app in cpu_results:
            cpu_h = cpu_results[app]['history']['y'].mean()
            cpu_n = cpu_results[app]['history']['y'].iloc[-1]
            cpu_p = cpu_results[app]['forecast'].tail(24)['yhat'].mean()

        if app in mem_results:
            mem_h = mem_results[app]['history']['y'].mean()
            mem_n = mem_results[app]['history']['y'].iloc[-1]
            mem_p = mem_results[app]['forecast'].tail(24)['yhat'].mean()
            
        c_chg = ((cpu_p - cpu_h) / cpu_h * 100) if cpu_h > 0 else 0
        m_chg = ((mem_p - mem_h) / mem_h * 100) if mem_h > 0 else 0
        ov_chg = c_chg if abs(c_chg) > abs(m_chg) else m_chg
        
        trend = "UP" if ov_chg > 5 else ("DOWN" if ov_chg < -5 else "FLAT")
        app_name = (app[:22] + '..') if len(app) > 24 else app

        print(f"| {app_name:<25} | {cpu_h:>6.2f} {cpu_n:>7.2f} {cpu_p:>7.2f} | {mem_h:>6.2f} {mem_n:>7.2f} {mem_p:>7.2f} | {trend:>9} {ov_chg:>10.1f}% |")
    print("="*113 + "\n")

def display_detailed_forecast(results, resource_type, top_n=3):
    if not results: return
    sorted_apps = sorted(results.items(), key=lambda x: x[1]['forecast'].tail(24)['yhat'].mean(), reverse=True)[:top_n]
    unit = "Cores" if resource_type == "cpu" else "MB"
    
    print(f"DETAILED {resource_type.upper()} FORECAST (Top {top_n})")
    for app, data in sorted_apps:
        hist = data['history']['y'].mean()
        curr = data['history']['y'].iloc[-1]
        print("-" * 80)
        print(f" Deployment: {app} | Current: {curr:.2f} {unit} | History: {hist:.2f} {unit}")
        print("-" * 80)
        print(f"| {'TIME':<16} | {'PREDICTED':>15} | {'MIN (Lower)':>15} | {'MAX (Upper)':>15} |")
        
        forecast = data['forecast'].tail(24)
        for i in range(0, 24, 4):
            r = forecast.iloc[i]
            print(f"| {r['ds'].strftime('%m/%d %H:%M'):<16} | {r['yhat']:>10.2f} {unit:<4} | {r['yhat_lower']:>10.2f} {unit:<4} | {r['yhat_upper']:>10.2f} {unit:<4} |")
        print("")

# Metrics Update Layer 
def update_prometheus_metrics(cpu_results, mem_results):
    print("[INFO] Updating Prometheus Gauges...")
    count = 0
    now = datetime.now()
    
    # Update CPU Gauges
    for app, data in cpu_results.items():
        future_df = data['forecast'][data['forecast']['ds'] > now].head(24)
        for _, row in future_df.iterrows():
            h = int((row['ds'] - now).total_seconds() / 3600) + 1
            if 1 <= h <= 24:
                cpu_forecast_gauge.labels(deployment=app, hours_ahead=str(h)).set(max(0, row['yhat']))
        count += 1

    # Update Memory Gauges
    for app, data in mem_results.items():
        future_df = data['forecast'][data['forecast']['ds'] > now].head(24)
        for _, row in future_df.iterrows():
            h = int((row['ds'] - now).total_seconds() / 3600) + 1
            if 1 <= h <= 24:
                mem_forecast_gauge.labels(deployment=app, hours_ahead=str(h)).set(max(0, row['yhat']))
        count += 1
        
    last_run_gauge.set(time.time())
    print(f"[INFO] Successfully updated metrics for {count} deployment curves.")

# Main Loop 
def update_loop():
    print("\n" + "*"*60)
    print(f"STARTING FORECAST RUN: {datetime.now()}")
    print("*"*60)

    # 1. Fetch
    cpu_data = get_deployment_metrics(NAMESPACE, hours=168, metric_type="cpu")
    mem_data = get_deployment_metrics(NAMESPACE, hours=168, metric_type="memory")

    if not cpu_data and not mem_data:
        print("[ERROR] Failed to fetch data. Retrying next cycle.")
        return

    # 2. Forecast
    cpu_res = generate_forecasts(cpu_data)
    mem_res = generate_forecasts(mem_data)

    # 3. Visualize (Logs)
    display_terminal_summary(cpu_res, mem_res)
    if cpu_res: display_detailed_forecast(cpu_res, "cpu", top_n=2)
    if mem_res: display_detailed_forecast(mem_res, "memory", top_n=2)

    # 4. Update Metrics
    update_prometheus_metrics(cpu_res, mem_res)
    print(f"[INFO] Run complete. Sleeping for {UPDATE_INTERVAL}s...")

def main():
    print(f"🚀 Starting Forecasting Service on port {EXPORTER_PORT}...")
    try:
        start_http_server(EXPORTER_PORT)
    except Exception as e:
        print(f"[FATAL] Failed to start HTTP server: {e}")
        sys.exit(1)
    
    while True:
        update_loop()
        time.sleep(UPDATE_INTERVAL)

if __name__ == "__main__":
    main()