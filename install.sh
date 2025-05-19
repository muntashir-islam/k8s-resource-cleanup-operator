#!/bin/bash
# install.sh - Script to install the Cleanup Operator

set -e  # Exit on any error

echo "Step 1: Removing any failed installations..."
# Try uninstalling first
helm uninstall cleanup-operator 2>/dev/null || true

# Check if release is still in pending-install or pending-upgrade state
if helm list -q | grep -q "cleanup-operator"; then
  echo "Release still exists. Attempting to force deletion with Helm secrets..."
  kubectl get secret -l owner=helm,name=cleanup-operator -o name | xargs kubectl delete 2>/dev/null || true
  
  # If helm 3, also check for helm secrets
  kubectl get secret -l owner=helm -l status=deployed -l name=cleanup-operator -o name | xargs kubectl delete 2>/dev/null || true
  
  # Additional check for any remaining helm secrets
  echo "Searching for any remaining Helm secrets for cleanup-operator..."
  HELM_SECRETS=$(kubectl get secrets --all-namespaces -o json | jq -r '.items[] | select(.metadata.name | test("sh\\.helm\\.release\\.v1\\.cleanup-operator\\..*")) | .metadata.namespace + "/" + .metadata.name')
  
  if [ ! -z "$HELM_SECRETS" ]; then
    echo "Found helm secrets to delete:"
    echo "$HELM_SECRETS"
    
    echo "$HELM_SECRETS" | while read -r secret; do
      if [ ! -z "$secret" ]; then
        echo "Deleting Helm secret: $secret"
        kubectl delete secret -n $(echo $secret | cut -d '/' -f1) $(echo $secret | cut -d '/' -f2) || true
      fi
    done
  fi
fi

echo "Step 2: Applying CRD definition..."
kubectl apply -f cleanup-crd.yaml

echo "Step 3: Waiting for CRD to be established..."
kubectl wait --for condition=established --timeout=60s crd/cleanups.resources.muntashir.com

echo "Step 4: Installing Helm chart (with CRD creation disabled)..."
# Set the current namespace for installation
CURRENT_NS=$(kubectl config view --minify -o jsonpath='{.contexts[0].context.namespace}' 2>/dev/null)
if [ -z "$CURRENT_NS" ]; then
  CURRENT_NS="default"
  echo "No namespace detected in current context, using namespace: $CURRENT_NS"
else
  echo "Installing in namespace: $CURRENT_NS"
fi

helm install cleanup-operator ./charts/cleanup-operator --set crd.create=false -n $CURRENT_NS

echo "Step 5: Creating the default Cleanup resource..."
cat <<EOF | kubectl apply -f -
apiVersion: resources.muntashir.com/v1
kind: Cleanup
metadata:
  name: default-cleanup
  namespace: $CURRENT_NS
spec:
  namespaces:
    - default
    - production
    - staging
  unusedThresholdHours: 2
  dryRun: true
EOF

echo "Installation complete! You can check the status with:"
echo "kubectl get pod -l app.kubernetes.io/name=cleanup-operator -n $CURRENT_NS"
echo "kubectl get cleanup default-cleanup -n $CURRENT_NS"