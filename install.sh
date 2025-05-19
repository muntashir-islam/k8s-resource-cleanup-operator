#!/bin/bash
# install.sh - Script to install the Cleanup Operator

set -e  # Exit on any error

echo "Step 1: Removing any failed installations..."
helm uninstall cleanup-operator || true

echo "Step 2: Applying CRD definition..."
kubectl apply -f cleanup-crd.yaml

echo "Step 3: Waiting for CRD to be established..."
kubectl wait --for condition=established --timeout=60s crd/cleanups.resources.muntashir.com

echo "Step 4: Installing Helm chart (with CRD creation disabled)..."
helm install cleanup-operator ./charts/cleanup-operator --set crd.create=false

echo "Step 5: Creating the default Cleanup resource..."
cat <<EOF | kubectl apply -f -
apiVersion: resources.muntashir.com/v1
kind: Cleanup
metadata:
  name: default-cleanup
  namespace: $(kubectl config view --minify -o jsonpath='{.contexts[0].context.namespace}' 2>/dev/null || echo "default")
spec:
  namespaces:
    - default
    - production
    - staging
  unusedThresholdHours: 2
  dryRun: true
EOF

echo "Installation complete! You can check the status with:"
echo "kubectl get pod -l app.kubernetes.io/name=cleanup-operator"
echo "kubectl get cleanup default-cleanup"