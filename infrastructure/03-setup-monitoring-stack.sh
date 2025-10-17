#!/bin/bash
#
# Script for initial setup of the monitring stack for
# Prometheus and Grafana
#
# Ref: https://helm.sh/docs/intro/install/#:~:text=Helm%20can%20be%20installed
# Ref: https://prometheus-community.github.io/helm-charts
# Ref: https://grafana.github.io/helm-charts

# Absolute path to the script directory
# This allows the script to be run from any directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
ROOT_DIR="$SCRIPT_DIR/../.." 

# Check if Helm is already installed
if command -v helm &> dev/null; then
    echo "Helm is already installed: $(helm version --short)"
else
    echo "Installing Helm..."

    curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 || 
    {
        echo "Failed to download Helm installer"; exit 1
    }
    chmod 700 get_helm.sh 
    ./get_helm.sh && rm -f get_helm.sh
    echo "Helm installed successfully: $(helm version --short)"
fi

# Check if cluster exist
if ! kubectl cluster-info &> /dev/null; then
    echo "No Kubernetes cluster not found. Run ./scripts/setup/setup-cluster.sh first"
    exit 1
fi 

# Add monitoring repositories
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts

# Update helm repositories
helm repo update

# Deploy Prometheus
helm upgrade --install prometheus prometheus-community/prometheus \
 --namespace monitoring \
 --create-namespace \
 --wait --timeout=300s

# Deploy Grafana
helm upgrade --install grafana grafana/grafana \
 --namespace monitoring \
 --create-namespace \
 --wait --timeout=300s

echo "Monitoring stack setup complete!"
