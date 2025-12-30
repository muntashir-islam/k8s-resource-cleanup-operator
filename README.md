# Kubernetes Stale Resource Cleanup Operator

A Kubernetes operator that automatically cleans up unused ConfigMaps and Secrets across your cluster to reduce clutter and improve resource management.

![Kubernetes](https://img.shields.io/badge/kubernetes-%23326ce5.svg?style=for-the-badge&logo=kubernetes&logoColor=white)
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)

## Overview

The Stale Resource Cleanup Operator monitors your Kubernetes cluster for unused ConfigMaps and Secrets, and automatically removes them based on configurable rules. A resource is considered "unused" when it's not referenced by any workload (Pod, Deployment, StatefulSet, DaemonSet) and has existed for longer than a specified time threshold.

### Key Features

- **Automated cleanup**: Scan and delete unused ConfigMaps and Secrets on a schedule
- **Safe by default**: Starts in dry-run mode to preview deletions before committing changes
- **Configurable**: Select namespaces, exclusion patterns, age thresholds and more
- **Kubernetes-native**: Uses Custom Resources for configuration and status reporting
- **Small footprint**: Minimal resource consumption (64Mi memory, 100m CPU requested)
- **Configurable Rules:**: Set which namespaces to monitor, age thresholds, exclusion patterns, etc.
- **Resource Reference Detection**: Intelligently detects resources referenced by
  - Pod volumes
  - Environment variables
  - Projected volumes
  - Image pull secrets
  - Service accounts
## Installation

### Prerequisites

- Kubernetes 1.19+

### Quick Start 

Install the Cleanup Operator with Helm:

```bash
# Clone the repository
git clone git@github.com:muntashir-islam/k8s-resource-cleanup-operator.git
cd k8s-resource-cleanup-operator
kubectl apply -f deployment.yaml
```
### Configuration

The operator can be configured through a ConfigMap or by modifying the Custom Resource:

### Using the ConfigMap
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: cleanup-operator-config
  namespace: cleanup-system
data:
  config.yaml: |
    namespaces:
      - default
      - production
      - staging
    cleanup_interval: 3600  # Seconds between cleanup cycles
    unused_threshold_hours: 24  # Only clean resources older than this
    dry_run: true  # Set to false for actual deletion
    exclude_patterns:
      - "kube-*"
      - "default-token-*"
    log_level: INFO
```

### Using Custom Resources

You can also configure the operator through the `Cleanup` Custom Resource:

```yaml
apiVersion: resources.muntashir.com/v1
kind: Cleanup
metadata:
  name: default-cleanup
  namespace: cleanup-system
spec:
  namespaces:
    - default
    - production
  unused_threshold_hours: 48
  dry_run: false
```

### Environment Variables
The operator also supports configuration via environment variables:

- CLEANUP_NAMESPACES: Comma-separated list of namespaces to monitor
- CLEANUP_INTERVAL: Seconds between cleanup cycles
- DRY_RUN: Set to "true" for testing without actual deletion


### Usage

### Monitoring the Operator
View the operator logs:

Apply the Custom Resource:

```bash
kubectl logs -n cleanup-system -l app.kubernetes.io/name=cleanup-operator
```

## Manual Cleanup Trigger
You can manually trigger a cleanup cycle by adding an annotation to the ConfigMap:
```bash
kubectl annotate configmap -n cleanup-system cleanup-operator-config cleanup.operator/trigger=now --overwrite
```

### Checking Status

View the status of your Cleanup resources:

```bash
kubectl get cleanups -n cleanup-system

NAME              STATUS      AGE
default-cleanup   Scheduled   1h
prod-cleanup      Triggered   5m
```

Check detailed results from a cleanup operation:

```bash
kubectl describe cleanup default-cleanup -n cleanup-system
```

### Manual Trigger

Trigger a cleanup manually by adding an annotation:

```bash
kubectl annotate cleanup default-cleanup -n cleanup-system cleanup.operator/trigger=now
```

Or update the CR with `force: true`:

```yaml
apiVersion: resources.muntashir.com/v1
kind: Cleanup
metadata:
  name: default-cleanup
  namespace: cleanup-system
spec:
  namespaces:
    - default
  unusedThresholdHours: 24
  dryRun: true
  force: true  # Triggers immediate cleanup
```

### Viewing Logs

Monitor the operator logs to see what's happening:

```bash
kubectl logs -f -l app.kubernetes.io/name=cleanup-operator -n cleanup-system
```
## Debugging
To troubleshoot the operator, you can temporarily:

- Set `log_level: DEBUG` in the ConfigMap
- Reduce `unused_threshold_hours` to 0 for testing
- Use `dry_run: true` for safe testing
  
## How It Works

The Cleanup Operator:

1. **Discovers Resources** - Scans all configmaps and secrets in selected namespaces
2. **Traces References** - Checks if each resource is referenced by any pods, deployments, daemonsets, or statefulsets
3. **Applies Filters** - Excludes resources matching exclusion patterns and those younger than the configured threshold
4. **Performs Cleanup** - Removes unused resources (or logs what would be removed in dry-run mode)

## Resource Reference Detection

- Volume mounts
- Environment variables
- Environment variable sources
- Image pull secrets
- Service account tokens

## Security Considerations

The operator requires appropriate RBAC permissions to function properly:

- `get`, `list`, `watch` permissions on pods, deployments, etc. to identify references
- `get`, `list`, `delete` permissions on secrets and configmaps for cleanup
- Access to CustomResourceDefinitions for operator functionality

Review the generated RBAC roles before deployment in production environments.

## Development

### Building from Source

```bash
# Clone the repository
git clone https://github.com/muntashir-islam/k8s-resource-cleanup-operator.git
cd cleanup-operator

# Build the Docker image
docker build -t your-registry/cleanup-operator:latest .

# Push the image
docker push your-registry/cleanup-operator:latest
```

### Local Development

For local development:

```bash
# Install required dependencies
pip install -r requirements.txt

# Run the operator locally (outside the cluster)
python cleanup_operator.py
```

## Troubleshooting

### Common Issues

1. **Operator not cleaning up resources**
   - Check if the operator is in dry-run mode (`kubectl get cm cleanup-operator-config -n cleanup-system -o yaml`)
   - Verify the resources meet the age threshold (`unused_threshold_hours`)
   - Check exclusion patterns aren't matching the resources

2. **Permission errors**
   - Ensure the operator service account has the required RBAC permissions
   - Check if you need cluster-level permissions for certain namespaces

3. **Operator pod crashes**
   - Check logs for errors: `kubectl logs -f deployment/cleanup-operator -n cleanup-system`
   - Verify the CRD is correctly deployed: `kubectl get crd cleanups.resources.muntashir.com`

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the project
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request
