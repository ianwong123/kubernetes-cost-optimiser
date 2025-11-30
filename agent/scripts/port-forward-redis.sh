#!/bin/bash
# Kubernetes redis port-forwarding script

NAMESPACE="databases"
SERVICE_NAME="redis-master"

if ! kubectl get svc "$SERVICE_NAME" -n "$NAMESPACE" &> /dev/null; then
    echo "Service $SERVICE_NAME not found in namespace $NAMESPACE"
    echo "Available services in $NAMESPACE:"
    kubectl get svc -n "$NAMESPACE"
    exit 1
fi

kubectl port-forward -n databases svc/redis-master 6379:6379