#!/bin/bash
#
# Script for initial setup of a sealed-secrets
# To encrypt secrets and store in git
# 
# Ref: https://github.com/bitnami-labs/sealed-secrets

# Absolute path to the script directory
# This allows the script to be run from any directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
ROOT_DIR="$SCRIPT_DIR/../.."  

# Add sealed-secrets repository
helm repo add sealed-secrets https://bitnami-labs.github.io/sealed-secrets
helm repo update

# Deploy Sealed Secrets
helm upgrade --install sealed-secrets sealed-secrets/sealed-secrets \
 --namespace kube-system \
 --create-namespace \
 --wait --timeout=300s

# Install kubeseal CLI
curl -OL "https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.29.0/kubeseal-0.29.0-linux-amd64.tar.gz"
tar -xvzf kubeseal-0.29.0-linux-amd64.tar.gz kubeseal
sudo install -m 755 kubeseal /usr/local/bin/kubeseal
kubeseal --version

echo "Sealed Secrets setup complete!"

