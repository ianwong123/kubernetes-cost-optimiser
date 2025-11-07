import pandas as pd
import requests
import json
import subprocess
from datetime import datetime, timedelta
from prophet import Prophet
import sys
import os

# This script predicts how much CPU and memory Kubernetes applications will need
# tomorrow based on how much they used historically

# It returns the following that will be pushed to Redis
# - CPU requests
# - CPU usage
# - CPU usage predictions
# - Memory requests
# - Memory usage
# - Memory usage predictions
# - Number of VMs fetched from cost-engine
# - Current hourly cost from cost-engine

# Configuration
PROMETHEUS_URL = "http://prometheus.local.io"
NAMESPACE = "default"

# Get all current resource requests
def get_current_resource_requests(namespace):
    """Fetch current CPU and memory requests"""

def get_vm_and_cost_info():
    """Fetch current number of VMs and hourly cost from cost-engine"""

        
# Get all deployment memory usage
def get_deployment_memory_usage(namespace, hours=168):
    """
    Get memory usage aggregated by deployment (not individual pods).
    This survives pod restarts and provides continuous timeseries data.
    """
    # As cluster is not running 24/7, pods restart only when machine is booted
    # Causing current running pods to not have enough history as previous pods only lived
    # for a few hours
    # We test by deployment level first, and find a solution to this issue
    
    # Aggregate by deployment label
    query = f'''
        sum by (app) (
            container_memory_working_set_bytes{{
                namespace="{namespace}",
                container!="POD",
                container!=""
            }}
        )
    '''
    
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=hours)
    
    print(f"Fetching {hours}h of memory data (aggregated by deployment)")
    print(f"Time range: {start_time.strftime('%Y-%m-%d %H:%M')} to {end_time.strftime('%Y-%m-%d %H:%M')}")
    
    response = requests.get(f"{PROMETHEUS_URL}/api/v1/query_range", params={
        'query': query,
        'start': start_time.timestamp(),
        'end': end_time.timestamp(),
        'step': '15m'
    })
    
    data = response.json()
    
    if data['status'] != 'success':
        print(f"Query failed: {data.get('error', 'Unknown error')}")
        return None
    
    if not data['data']['result']:
        print("No data returned from Prometheus")
        return None
    
    all_deployments_data = {}
    
    for result in data['data']['result']:
        deployment_name = result['metric'].get('app', 'unknown')
        
        timestamps = []
        values = []
        
        for timestamp, value in result['values']:
            dt = datetime.fromtimestamp(float(timestamp))
            memory_mb = float(value) / (1024 * 1024)
            timestamps.append(dt)
            values.append(memory_mb)
        
        # Skip if no valid data
        if not values or all(v <= 0 for v in values):
            continue
        
        df = pd.DataFrame({'ds': timestamps, 'y': values})
        all_deployments_data[deployment_name] = df
        
        print(f"   {deployment_name}: {len(df)} data points, avg {df['y'].mean():.1f} MB")
    
    print(f"\nCollected memory data for {len(all_deployments_data)} deployments")
    return all_deployments_data

# Get all deployment CPU usage
def get_deployment_cpu_usage(namespace, hours=168):
    """
    Get CPU usage (in cores) aggregated by deployment.
    Uses rate(container_cpu_usage_seconds_total[5m]) for accurate per-second usage.
    """
    query = f'''
        sum by (app) (
            rate(container_cpu_usage_seconds_total{{
                namespace="{namespace}",
                container!="POD",
                container!=""
            }}[5m])
        )
    '''
    
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=hours)
    
    print(f"Fetching {hours}h of CPU data (aggregated by deployment)")
    print(f"Time range: {start_time.strftime('%Y-%m-%d %H:%M')} to {end_time.strftime('%Y-%m-%d %H:%M')}")
    
    response = requests.get(f"{PROMETHEUS_URL}/api/v1/query_range", params={
        'query': query,
        'start': start_time.timestamp(),
        'end': end_time.timestamp(),
        'step': '15m'
    })
    
    data = response.json()
    
    if data['status'] != 'success':
        print(f"Query failed: {data.get('error', 'Unknown error')}")
        return None
    
    if not data['data']['result']:
        print("No CPU data returned from Prometheus")
        return None
    
    all_deployments_data = {}
    
    for result in data['data']['result']:
        deployment_name = result['metric'].get('app', 'unknown')
        
        timestamps = []
        values = []
        
        for timestamp, value in result['values']:
            dt = datetime.fromtimestamp(float(timestamp))
            cpu_cores = float(value)  # Already in cores
            timestamps.append(dt)
            values.append(cpu_cores)
        
        # Skip if no valid data
        if not values or all(v <= 0 for v in values):
            continue
        
        df = pd.DataFrame({'ds': timestamps, 'y': values})
        all_deployments_data[deployment_name] = df
        
        print(f"   {deployment_name}: {len(df)} data points, avg {df['y'].mean():.3f} cores")
    
    print(f"\nCollected CPU data for {len(all_deployments_data)} deployments")
    return all_deployments_data

# Forecasting
def forecast_all_deployments(all_deployments_data, forecast_hours=24):
    """
    Train Prophet and forecast for each deployment.
    """
    
    print(f"\nTraining forecasting models...")
    forecasts = {}
    failed = []
    
    for deployment_name, historical_df in all_deployments_data.items():
        try:
            data_points = len(historical_df)
            
            # Thresholds:
            if data_points < 12:
                failed.append((deployment_name, f"Too little data: {data_points} points"))
                continue

            # Use conservative settings for stability
            model = Prophet(
                changepoint_prior_scale = 0.01,
                interval_width = 0.90,
                daily_seasonality = False,
                weekly_seasonality = False
            )
            
            # Suppress Prophet's verbose output
            devnull = open(os.devnull, 'w')
            old_stdout = sys.stdout
            sys.stdout = devnull
            model.fit(historical_df)
            sys.stdout = old_stdout
            devnull.close()
            
            future = model.make_future_dataframe(periods=forecast_hours, freq='h')
            forecast = model.predict(future)
            
            forecasts[deployment_name] = {
                'model': model,
                'forecast': forecast,
                'historical': historical_df
            }
            
            print(f"     {deployment_name}: {data_points} points → forecast successful")
            
        except Exception as e:
            failed.append((deployment_name, str(e)))
    
    print(f"\nSuccessfully forecasted {len(forecasts)} deployments")
    if failed:
        print(f"Failed for {len(failed)} deployments:")
        for name, reason in failed:
            print(f"   - {name}: {reason}")
    
    return forecasts

# Fetch current VPA recommendations
def get_vpa_recommendations(namespace):
    """Get current VPA recommendations for both CPU and memory"""

    print("Fetching VPA recommendations...")

    try: 
        cmd = f"kubectl get vpa -n {namespace} -o json"
        result = subprocess.run(cmd.split(), capture_output = True, text = True)

        if result.returncode != 0:
            print("VPA not accessible")
            return {}

        vpa_data = json.loads(result.stdout)
        vpa_recommendations = {}

        for item in vpa_data.get('items', []):
            vpa_name = item['metadata']['name']

            # Remove 'vpa' prefix. eg,. vpa-adservice
            deployment_name = vpa_name.replace('vpa-', '')

            # Get container recommendations
            container_recs = item.get('status', {}).get('recommendation', {}).get('containerRecommendations', [])

            if container_recs:
                target = container_recs[0].get('target', {})
                
                # CPU recommendation
                cpu = target.get('cpu')
                cpu_cores = None
                if cpu:
                    if cpu.endswith('m'):
                        cpu_cores = float(cpu[:-1]) / 1000.0
                    else:
                        cpu_cores = float(cpu)
                
                # Memory recommendation
                memory = target.get('memory')
                memory_mb = None
                if memory:
                    if memory.endswith('Mi'):
                        memory_mb = float(memory[:-2])
                    elif memory.endswith('Gi'):
                        memory_mb = float(memory[:-2]) * 1024
                    else:
                        memory_mb = float(memory) / (1024 * 1024)  

                vpa_recommendations[deployment_name] = {
                    'cpu': cpu_cores,
                    'memory': memory_mb
                }
                print(f"     {deployment_name}: CPU={cpu_cores} cores, Memory={memory_mb:.0f} MB")

        print(f"   Loaded {len(vpa_recommendations)} VPA recommendations")
        return vpa_recommendations

    except Exception as e:
        print(f"     Error fetching VPA: {e}")
        return {}

# Display a combined summary table
def display_combined_summary(mem_forecasts, cpu_forecasts, vpa_recommendations):  
    """
    Display clean summary table for all deployments with CPU, memory, and VPA.
    """
    
    print("\n" + "="*140)
    print("RESOURCE FORECAST SUMMARY - NEXT 24 HOURS")
    print("="*140)
    print(f"{'Deployment':<25} {'CPU Hist':>10} {'CPU Pred':>10} {'Mem Hist':>10} {'Mem Pred':>10} {'Trend':>8} {'VPA CPU':>10} {'VPA Mem':>10}")
    print("-"*140)
    
    all_deployments = set(mem_forecasts.keys()) | set(cpu_forecasts.keys())
    summary_data = []
    
    for deployment_name in sorted(all_deployments):
        # CPU metrics
        cpu_hist = cpu_pred = 0.0
        if deployment_name in cpu_forecasts:
            cpu_hist = cpu_forecasts[deployment_name]['historical']['y'].mean()
            cpu_pred = cpu_forecasts[deployment_name]['forecast'].tail(24)['yhat'].mean()
        
        # Memory metrics
        mem_hist = mem_pred = 0.0
        if deployment_name in mem_forecasts:
            mem_hist = mem_forecasts[deployment_name]['historical']['y'].mean()
            mem_pred = mem_forecasts[deployment_name]['forecast'].tail(24)['yhat'].mean()
        
        # Trend (based on combined CPU + memory change)
        cpu_trend_pct = ((cpu_pred - cpu_hist) / cpu_hist * 100) if cpu_hist > 0 else 0
        mem_trend_pct = ((mem_pred - mem_hist) / mem_hist * 100) if mem_hist > 0 else 0
        overall_trend = max(cpu_trend_pct, mem_trend_pct)
        
        if overall_trend > 10:
            trend = "UP"
        elif overall_trend < -10:
            trend = "DOWN"
        else:
            trend = "FLAT"
        
        # VPA values
        vpa_info = vpa_recommendations.get(deployment_name, {})
        vpa_cpu = f"{vpa_info.get('cpu', 0):.3f}" if vpa_info.get('cpu') is not None else "N/A"
        vpa_mem = f"{vpa_info.get('memory', 0):.0f}" if vpa_info.get('memory') is not None else "N/A"
        
        name_short = deployment_name[:23] + '..' if len(deployment_name) > 25 else deployment_name
        print(f"{name_short:<25} {cpu_hist:>9.3f} {cpu_pred:>9.3f} {mem_hist:>9.1f} {mem_pred:>9.1f} {trend:>8} {vpa_cpu:>10} {vpa_mem:>10}")
        summary_data.append({
            'deployment': deployment_name,
            'cpu_hist': cpu_hist,
            'cpu_pred': cpu_pred,
            'mem_hist': mem_hist,
            'mem_pred': mem_pred,
            'trend': trend
        })
    
    print("="*140)
    return summary_data

# Display a detail forecast table
def display_detailed_forecast(forecasts, resource_type, summary_data, top_n=3):
    """
    Show detailed 24h forecast for top N deployments for a given resource type.
    resource_type: 'cpu' or 'memory'
    """
    
    print(f"\nDETAILED {resource_type.upper()} FORECAST")
    print("="*110)
    
    # Sort by predicted usage
    if resource_type == 'cpu':
        top_deployments = sorted(summary_data, key=lambda x: x['cpu_pred'], reverse=True)[:top_n]
    else:
        top_deployments = sorted(summary_data, key=lambda x: x['mem_pred'], reverse=True)[:top_n]
    
    for i, deployment_info in enumerate(top_deployments, 1):
        deployment_name = deployment_info['deployment']
        if deployment_name not in forecasts:
            continue
            
        data = forecasts[deployment_name]
        forecast_df = data['forecast']
        future_forecast = forecast_df.tail(24)
        
        # Get current usage (latest data point)
        historical_df = data['historical']
        current_usage = historical_df['y'].iloc[-1] if len(historical_df) > 0 else 0
        
        print(f"\n{i}. {deployment_name}")
        print(f"Current usage: {current_usage:.3f} cores" if resource_type == 'cpu' else f"Current usage: {current_usage:.1f} MB")
        print("-"*90)
        print(f"{'Time':<20} {'Predicted':>15} {'Lower Bound':>15} {'Upper Bound':>15}")
        print("-"*90)
        
        # Show every 4 hours
        for idx in range(0, 24, 4):
            row = future_forecast.iloc[idx]
            time_str = row['ds'].strftime('%m/%d %H:%M')
            if resource_type == 'cpu':
                print(f"{time_str:<20} {row['yhat']:>12.3f} {row['yhat_lower']:>12.3f} {row['yhat_upper']:>12.3f}")
            else:
                print(f"{time_str:<20} {row['yhat']:>12.1f} MB {row['yhat_lower']:>12.1f} MB {row['yhat_upper']:>12.1f} MB")
        
        if resource_type == 'cpu':
            print(f"\nHistorical Avg CPU: {deployment_info['cpu_hist']:.3f} cores")
            print(f"Predicted Avg CPU:  {deployment_info['cpu_pred']:.3f} cores")
            print(f"Current CPU:        {current_usage:.3f} cores")
        else:
            print(f"\nHistorical Avg Mem: {deployment_info['mem_hist']:.1f} MB")
            print(f"Predicted Avg Mem:  {deployment_info['mem_pred']:.1f} MB")
            print(f"Current Memory:     {current_usage:.1f} MB")

def main():
    print("="*110)
    print("KUBERNETES RESOURCE FORECASTING ENGINE")
    print("="*110)
    
    # Step 1: Fetch data (aggregated by deployment)
    memory_data = get_deployment_memory_usage(NAMESPACE, hours=168)
    cpu_data = get_deployment_cpu_usage(NAMESPACE, hours=168)
    
    if not memory_data:
        print("\nNo memory data available. Troubleshooting steps:")
        print("   1. Verify Prometheus is accessible: curl http://prometheus.local.io/api/v1/query?query=up")
        print("   2. Check if pods are running: kubectl get pods -n default")
        print("   3. Wait for metrics to accumulate (needs at least 2 days)")
        print("   4. Verify deployment labels exist: kubectl get deployments -n default")
        return
        
    if not cpu_data:
        print("\nNo CPU data available. Same troubleshooting applies.")
        return

    # Step 2: Get VPA recommendations
    vpa_recommendations = get_vpa_recommendations(NAMESPACE)

    # Step 3: Generate forecasts
    memory_forecasts = forecast_all_deployments(memory_data, forecast_hours=24)
    cpu_forecasts = forecast_all_deployments(cpu_data, forecast_hours=24)
    
    if not memory_forecasts and not cpu_forecasts:
        print("\nNo successful forecasts generated")
        print("This usually means insufficient data (need at least 12 data points = 3 hours)")
        return
    
    # Step 4: Display results
    summary_data = display_combined_summary(memory_forecasts, cpu_forecasts, vpa_recommendations)
    
    if cpu_forecasts:
        display_detailed_forecast(cpu_forecasts, 'cpu', summary_data, top_n=3)
    if memory_forecasts:
        display_detailed_forecast(memory_forecasts, 'memory', summary_data, top_n=3)
    
    print("\n" + "="*110)
    print("FORECASTING COMPLETE")
    print("="*110)
    #print(f"\nTotal deployments analysed: {len(set(memory_forecasts.keys()) | set(cpu_forecasts.keys()))}")
    print(f"Forecast horizon: 24 hours")
    print(f"Confidence interval: 90%")


if __name__ == "__main__":
    main()