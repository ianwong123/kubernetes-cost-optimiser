import pandas as pd
import requests
from datetime import datetime, timedelta
from prophet import Prophet
import matplotlib.pyplot as plt

# Configuration
PROMETHEUS_URL = "http://prometheus.local.io"
NAMESPACE = "default"

# Pull memory usage from Prometheus
def get_all_pods_memory_usage(namespace, hours=168):
    """Get memory usage for all pods in a namespace"""

    # Query
    query = f'''avg_over_time(container_memory_working_set_bytes{{namespace="{namespace}",container!="POD"}}[1m])'''
    
    # Time range up to current moment
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=hours)

    print(f"Fetching memory data for all pods in {namespace}")
    print(f"Time range: {start_time} to {end_time}")

    # Send a request to Prometheus
    response = requests.get(f"{PROMETHEUS_URL}/api/v1/query_range", params={
        'query': query,
        'start': start_time.timestamp(),
        'end': end_time.timestamp(),
        'step': '15m'
    })

    data = response.json()  

    if data['status'] != 'success' or not data['data']['result']:
        print("No data returned from Prometheus")
        return None

    # Process all pods
    all_pods_data = {}

    # Return data for each pod separately
    for result in data['data']['result']:
        pod_name = result['metric']['pod']

        timestamps = []
        values = []

        for timestamp, value in result['values']:
            dt = datetime.fromtimestamp(float(timestamp))
            # Convert to MB
            memory_mb = float(value) / (1024 * 1024)
            timestamps.append(dt)
            values.append(memory_mb)

        # Initialise DataFrame 
        df = pd.DataFrame({'ds': timestamps, 'y': values})
        all_pods_data[pod_name] = df

        print(f"     {pod_name}: {len(df)} data points, {df['y'].mean():.1f} MB avg") 
        
    return all_pods_data

# Forecast for each pod
def forecast_all_pods(all_pods_data, forecast_hours=24):
    """Forecast memory usage for each pod"""

    forecasts = {}

    # Analyse each pod separately
    for pod_name, historical_df in all_pods_data.items():
        print(f"Training model for {pod_name}")

        try:
            model = Prophet(
                changepoint_prior_scale=0.05,
                interval_width=0.80,
                daily_seasonality=True
            )

            model.fit(historical_df)

            # Create future timeframe
            future = model.make_future_dataframe(periods=forecast_hours, freq='h')
            
            # Make prediction
            forecast = model.predict(future)

            forecasts[pod_name] = {
                'model': model,
                'forecast': forecast,
                'historical': historical_df
            }

            print(f"    Forecasting complete for {pod_name}")

        except Exception as e:
            print(f"    Failed for {pod_name}: {e}")

    return forecasts

# A function to test displaying forecast tables
# yhat = predicted value
# yhat_lower = lower bound of the predicted value
# yhat_upper = upper bound of the predicted value   
# trend = overall direction of the time series ignoring seasonality and holidays
# trend_lower = uncertainty levels
# trend_upper = uncertainty levels
def display_forecast_tables(forecasts, top_n=3):
    """Display the forecast tables for the top N memory-intensive pods"""
    
    print("\n" + "="*60)
    print("FORECAST TABLES - NEXT 24 HOURS")
    print("="*60)
    
    # Find pods with highest average memory usage
    pod_avgs = {}
    for pod_name, data in forecasts.items():
        avg_usage = data['historical']['y'].mean()
        pod_avgs[pod_name] = avg_usage
    
    # Top N most memory-intensive pods
    top_pods = sorted(pod_avgs.items(), key=lambda x: x[1], reverse=True)[:top_n]
    
    for pod_name, avg_usage in top_pods:
        data = forecasts[pod_name]
        forecast_df = data['forecast']
        
        # Get only future predictions (last 24 rows)
        future_forecast = forecast_df.tail(24)
        
        print(f"\n {pod_name} - Memory Forecast (MB)")
        print("-" * 50)
        
        # Display simplified table
        simplified = future_forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].copy()
        simplified['ds'] = simplified['ds'].dt.strftime('%m/%d %H:%M')
        simplified['yhat'] = simplified['yhat'].round(1)
        simplified['yhat_lower'] = simplified['yhat_lower'].round(1)
        simplified['yhat_upper'] = simplified['yhat_upper'].round(1)
        
        print(simplified.to_string(index=False))
        print(f"Historical Average: {avg_usage:.1f} MB")


def main():
    
    all_pods_data = get_all_pods_memory_usage(NAMESPACE, hours=168)  
    
    if all_pods_data is None:
        print("No data fetched from Prometheus")
        return

    forecasts = forecast_all_pods(all_pods_data, forecast_hours=24)

    if not forecasts:
        print("No successful forecasts")
        return
    
    print(f"\n Generated forecasts for {len(forecasts)} pods")
    
    # Test display forecast tables
    display_forecast_tables(forecasts, top_n=3)


if __name__ == "__main__":
    main()
