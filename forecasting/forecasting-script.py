import pandas as pd
import requests
import json
import subprocess
from datetime import datetime, timedelta
from prophet import Prophet
import sys
import os

# This script predicts how much memory Kubernetes application will need
# tomorrow based on how much they used yesterday

# Configuration
PROMETHEUS_URL = "http://prometheus.local.io"
NAMESPACE = "default"

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
    
    print(f"\nCollected data for {len(all_deployments_data)} deployments")
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

            #elif data_points < 24:
             #   print(f"{deployment_name}: Low data ({data_points} points), attempting forecast...")
            
            # For now, a very small dataset, we could use a simpler model
            # Stabler setting to prevent overfitting
            #if data_points < 48:
             #   model = Prophet(
                    # Set it to a more conservative
              #      changepoint_prior_scale = 0.01,
                    # Set a higher uncertainty level  
               #     interval_width = 0.90,          
                    # Skip daily and weekly patterns for now
                #    daily_seasonality = False,       
                 #   weekly_seasonality = False
                #)

            # Use consevative settings for now
            # Play around more later
            model = Prophet(
                changepoint_prior_scale = 0.01,
                interval_width = 0.00,
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
    """Get current VPA recommendations"""

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

            # Get memory recommendation
            container_recs = item.get('status', {}).get('recommendation', {}).get('containerRecommendations', [])

            if container_recs:
                 memory = container_recs[0].get('target', {}).get('memory')
                 if memory: 
                    # Convert to MB
                    if memory.endswith('Mi'):
                        memory_mb = float(memory[:-2])
                    elif memory.endswith('Gi'):
                        memory_mb = float(memory[:-2]) * 1024
                    else:
                        memory_mb = float(memory) / (1024 * 1024)  

                    vpa_recommendations[deployment_name] = memory_mb
                    print(f"     {deployment_name}: {memory_mb:.0f} MB")

        print(f"   Loaded {len(vpa_recommendations)} VPA recommendations")
        return vpa_recommendations

    except Exception as e:
        print(f"     Error fetching VPA: {e}")
        return {}

# Display a summary table
def display_summary_table(forecasts, vpa_recommendations):  
    """
    Display clean summary table for all deployments and VPA recommendations.
    """
    
    print("\n" + "="*110)
    print("MEMORY FORECAST SUMMARY - NEXT 24 HOURS")
    print("="*110)
    print(f"{'Deployment':<45} {'Hist. Avg':>12} {'Pred. Avg':>12} {'P80 Upper':>12} {'Trend':>8}")
    print("-"*110)
    
    summary_data = []
    
    for deployment_name, data in forecasts.items():
        historical_df = data['historical']
        forecast_df = data['forecast']
        
        # Calculate metrics
        historical_avg = historical_df['y'].mean()
        future_forecast = forecast_df.tail(24)
        predicted_avg = future_forecast['yhat'].mean()
        predicted_p80 = future_forecast['yhat_upper'].quantile(0.80)
        
        # Add 10% safety buffer
        #recommended = predicted_p80 * 1.10 
        
        # Get VPA recommendations
        vpa_rec = vpa_recommendations.get(deployment_name, None)

        # Determine trend
        trend_diff = predicted_avg - historical_avg
        trend_pct = (trend_diff / historical_avg * 100) if historical_avg > 0 else 0
        
        if trend_pct > 10:
            trend = "UP"
        elif trend_pct < -10:
            trend = "DOWN"
        else:
            trend = "FLAT"
        
        summary_data.append({
            'deployment': deployment_name,
            'historical': historical_avg,
            'predicted': predicted_avg,
            'p80_upper': predicted_p80,
            'trend': trend,
            'trend_pct': trend_pct
        })
    
    # Sort by predicted usage (highest first)
    summary_data.sort(key=lambda x: x['predicted'], reverse=True)
    
    # Print rows
    for row in summary_data:
        
        name_short = row['deployment'][:43] + '..' if len(row['deployment']) > 45 else row['deployment']
        print(f"{name_short:<45} {row['historical']:>9.1f} MB {row['predicted']:>9.1f} MB "
              f"{row['p80_upper']:>9.1f} MB {row['trend']:>8}")  
    
    print("="*110)
    
    return summary_data

# Display a detail forecast table
def display_detailed_forecast(forecasts, summary_data, top_n=3):
    """
    Show detailed 24h forecast for top N memory-intensive deployments.
    """
    
    print(f"\nDETAILED FORECAST - TOP {top_n} MEMORY-INTENSIVE DEPLOYMENTS")
    print("="*110)
    
    # Get top N deployments
    top_deployments = summary_data[:top_n]
    
    for i, deployment_info in enumerate(top_deployments, 1):
        deployment_name = deployment_info['deployment']
        data = forecasts[deployment_name]
        forecast_df = data['forecast']
        future_forecast = forecast_df.tail(24)
        
        print(f"\n{i}. {deployment_name}")
        print("-"*90)
        print(f"{'Time':<20} {'Predicted':>15} {'Lower Bound':>15} {'Upper Bound':>15}")
        print("-"*90)
        
        # Show every 4 hours (6 rows instead of 24)
        for idx in range(0, 24, 4):
            row = future_forecast.iloc[idx]
            time_str = row['ds'].strftime('%m/%d %H:%M')
            print(f"{time_str:<20} {row['yhat']:>12.1f} MB {row['yhat_lower']:>12.1f} MB {row['yhat_upper']:>12.1f} MB")
        
        print(f"\nHistorical Average: {deployment_info['historical']:.1f} MB")
        print(f"Predicted Average:  {deployment_info['predicted']:.1f} MB ({deployment_info['trend_pct']:+.1f}%)")
        #print(f"Recommended Request: {deployment_info['recommended']:.1f} MB")


def main():
    print("="*110)
    print("KUBERNETES MEMORY FORECASTING ENGINE")
    print("="*110)
    
    # Step 1: Fetch data (aggregated by deployment)
    all_deployments_data = get_deployment_memory_usage(NAMESPACE, hours = 168)
    
    if not all_deployments_data:
        print("\nNo data available. Troubleshooting steps:")
        print("   1. Verify Prometheus is accessible: curl http://prometheus.local.io/api/v1/query?query=up")
        print("   2. Check if pods are running: kubectl get pods -n default")
        print("   3. Wait for metrics to accumulate (needs at least 2 days)")
        print("   4. Verify deployment labels exist: kubectl get deployments -n default")
        return
    

    vpa_recommendations = get_vpa_recommendations(NAMESPACE)

    # Step 2: Generate forecasts
    forecasts = forecast_all_deployments(all_deployments_data, forecast_hours = 24)
    
    if not forecasts:
        print("\nNo successful forecasts generated")
        print("This usually means insufficient data (need at least 48 data points = 2 days)")
        return
    
    # Step 3: Display results
    summary_data = display_summary_table(forecasts, vpa_recommendations)
    display_detailed_forecast(forecasts, summary_data, top_n = 3)
    
    print("\n" + "="*110)
    print("FORECASTING COMPLETE")
    print("="*110)
    print(f"\nTotal deployments analysed: {len(forecasts)}")
    print(f"Forecast horizon: 24 hours")
    print(f"Confidence interval: 90%")


if __name__ == "__main__":
    main()