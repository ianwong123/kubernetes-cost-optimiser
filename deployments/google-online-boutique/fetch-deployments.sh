#!/bin/bash
#
# This script fetches all current/updated deployments in default namespace
# and removes dynamic fields such as timeStamps, versionResource, etc,.
#

for d in $(kubectl get deployments -n default -o jsonpath='{.items[*].metadata.name}'); do
    kubectl get deployment $d -n default -o yaml | \
    yq eval 'del(.metadata.creationTimestamp,
                 .metadata.resourceVersion,
                 .metadata.uid,
                 .metadata.annotations."deployment.kubernetes.io/revision",
                 .metadata.annotations."kubectl.kubernetes.io/last-applied-configuration",
                 .metadata.generation,
                 .status)' - > "./base/${d}.yaml"
done

echo "Cleaned deployment files saved to base/"