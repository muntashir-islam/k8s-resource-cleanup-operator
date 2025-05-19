#!/bin/bash
# uninstall.sh - Script to uninstall the Cleanup Operator

set -e  # Exit on any error

echo "-----------------------------------------------------"
echo "Cleanup Operator Uninstallation"
echo "-----------------------------------------------------"

# Function to print step information
print_step() {
  echo
  echo "STEP: $1"
  echo "-----------------------------------------------------"
}

# Function to handle errors
handle_error() {
  echo "ERROR: $1"
  echo "Continuing with uninstallation..."
}

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
  echo "kubectl not found. Please install kubectl and try again."
  exit 1
fi

# Check if helm is available
if ! command -v helm &> /dev/null; then
  echo "helm not found. Please install helm and try again."
  exit 1
fi

# Get namespace where operator is installed (default to "default" if not specified)
NAMESPACE=$(kubectl config view --minify -o jsonpath='{.contexts[0].context.namespace}' 2>/dev/null || echo "default")
echo "Using namespace: $NAMESPACE"

print_step "1. Removing Cleanup custom resources"
# List and delete all Cleanup CRs in all namespaces
echo "Searching for Cleanup resources in all namespaces..."
CLEANUP_RESOURCES=$(kubectl get cleanups --all-namespaces -o jsonpath='{range .items[*]}{.metadata.namespace}{" "}{.metadata.name}{"\n"}{end}' 2>/dev/null || echo "")

if [ -z "$CLEANUP_RESOURCES" ]; then
  echo "No Cleanup resources found."
else
  echo "Found Cleanup resources:"
  echo "$CLEANUP_RESOURCES"
  echo "Deleting Cleanup resources..."
  
  # Parse and delete each resource
  echo "$CLEANUP_RESOURCES" | while read -r line; do
    if [ -n "$line" ]; then
      NS=$(echo $line | cut -d' ' -f1)
      NAME=$(echo $line | cut -d' ' -f2)
      echo "Deleting Cleanup '$NAME' in namespace '$NS'..."
      kubectl delete cleanup $NAME -n $NS --timeout=60s || handle_error "Failed to delete Cleanup $NAME in namespace $NS"
    fi
  done
fi

print_step "2. Uninstalling Helm release"
# Uninstall the Helm release
echo "Uninstalling Cleanup Operator Helm release..."
helm uninstall cleanup-operator -n $NAMESPACE || handle_error "Failed to uninstall Helm release. It might not exist."

print_step "3. Removing deployment resources if they still exist"
# Delete any remaining operator resources
RESOURCES=("deployment/cleanup-operator" "configmap/cleanup-operator-config" "serviceaccount/cleanup-operator")
for RESOURCE in "${RESOURCES[@]}"; do
  echo "Checking for $RESOURCE..."
  if kubectl get $RESOURCE -n $NAMESPACE &>/dev/null; then
    echo "Resource exists. Deleting $RESOURCE..."
    kubectl delete $RESOURCE -n $NAMESPACE --timeout=30s || handle_error "Failed to delete $RESOURCE"
  else
    echo "Resource $RESOURCE not found. Skipping."
  fi
done

print_step "4. Removing RBAC resources"
# Remove RBAC resources
RBAC_RESOURCES=(
  "clusterrole/cleanup-operator"
  "clusterrolebinding/cleanup-operator"
  "role/cleanup-operator-namespace"
  "rolebinding/cleanup-operator-namespace"
)

for RESOURCE in "${RBAC_RESOURCES[@]}"; do
  echo "Checking for $RESOURCE..."
  if kubectl get $RESOURCE &>/dev/null; then
    echo "Resource exists. Deleting $RESOURCE..."
    kubectl delete $RESOURCE --timeout=30s || handle_error "Failed to delete $RESOURCE"
  else
    echo "Resource $RESOURCE not found. Skipping."
  fi
done

# Ask user if they want to remove the CRD
print_step "5. Removing the CustomResourceDefinition"
echo "WARNING: Removing the CRD will delete all Cleanup resources and their data."
read -p "Do you want to remove the 'cleanups.resources.muntashir.com' CRD? (y/N): " REMOVE_CRD

if [[ $REMOVE_CRD =~ ^[Yy]$ ]]; then
  echo "Removing the CustomResourceDefinition..."
  kubectl delete crd cleanups.resources.muntashir.com --timeout=60s || handle_error "Failed to delete CRD"
else
  echo "Skipping CRD removal. You can manually remove it later with:"
  echo "kubectl delete crd cleanups.resources.muntashir.com"
fi

echo
echo "-----------------------------------------------------"
echo "Uninstallation completed!"
echo "-----------------------------------------------------"
echo
echo "If you notice any remaining resources, you can remove them manually."
echo "To check for remaining resources, run:"
echo "kubectl get all -l app.kubernetes.io/name=cleanup-operator -A"
echo