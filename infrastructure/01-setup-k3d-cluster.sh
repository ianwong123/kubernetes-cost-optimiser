#!/bin/bash
#
# Script for initial setup of a k3d cluster for demo-cost-optimiser
# Checks if docker, k3d, and kubectl are installed and running
# Creates the cluster if it doesn't already exist

# Absolute path to the script directory
# This allows the script to be run from any directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
ROOT_DIR="$SCRIPT_DIR/../.."  

# Check if docker engine is running
if ! docker info &> /dev/null; then
  echo "Docker engine isn't running. Please start Docker and try again!"  
  exit 1
fi

# Check if k3d is installed
if ! command -v k3d &> /dev/null; then
  echo "k3d could not be found. Please install k3d and try again!"
  exit 1
fi

# Check if kubectl is installed
if ! command -v kubectl &> /dev/null; then
  echo "kubectl could not be found. Please install kubectl and try again!"
  exit 1
fi

# Check if cluster already exist
if k3d cluster list | grep -q demo-cost-optimiser; then
  echo "Cluster demo-cost-optimiser already exists!"
  exit 1  
else
  # Setup cluster
  k3d cluster create --config k3d-config.yaml --timeout 60s

  echo "Cluster setup complete!"
fi

# Display node information
kubectl get nodes -o wide

