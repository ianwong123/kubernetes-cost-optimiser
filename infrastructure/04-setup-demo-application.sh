#!/bin/bash
#
# This script is an initial set up for the demo application that will used in the cluster
# The demo application is an Online Boutique Store by Google Cloud Platform
# for testing kubernetes applications and microservices
# 
# The application can be accessed at demo.boutique.local.io locally after
# configuring ingress and adding the following entry to Windows' /etc/hosts file:
#
# 127.0.0.1 demo.boutique.local.io
#
# Official demo application: https://github.com/GoogleCloudPlatform/microservices-demo
# Kubernetes manifests: https://github.com/GoogleCloudPlatform/microservices-demo/blob/main/release/kubernetes-manifests.yaml

# Deploy the demo application
kubectl apply -f https://raw.githubusercontent.com/GoogleCloudPlatform/microservices-demo/main/release/kubernetes-manifests.yaml

# Wait for frontend pod to be ready
kubectl wait --for=condition=ready pod -l app=frontend --timeout=300s

# Apply ingress 
kubectl apply -f demo-app-ingress.yaml

echo "Demo application setup complete!"