#!/bin/bash
# Script to generate vpa for all default deployments

output="vpa.yaml"
> "$output"

kubectl get deployments -n default -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}' | while read name; do
    cat <<EOF >> "$output"
---
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: vpa-$name
  namespace: default
  labels:
    app: $name
    managed-by: vpa-controller
spec:
  targetRef:
    apiVersion: "apps/v1"
    kind: Deployment
    name: $name
  updatePolicy:
    updateMode: "Off"
EOF
done