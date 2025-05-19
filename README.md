# Kubernetes Cleanup Operator

A Kubernetes operator that automatically identifies and removes unused ConfigMaps and Secrets to keep your clusters tidy and resource-efficient.

![Kubernetes](https://img.shields.io/badge/kubernetes-%23326ce5.svg?style=for-the-badge&logo=kubernetes&logoColor=white)
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Helm](https://img.shields.io/badge/helm-%230F1689.svg?style=for-the-badge&logo=helm&logoColor=white)

## Overview

The Kubernetes Cleanup Operator helps you maintain a clean Kubernetes environment by detecting and removing ConfigMaps and Secrets that are no longer referenced by any workloads. This reduces cluster clutter and helps manage resources more efficiently.

### Key Features

- **Automated cleanup**: Scan and delete unused ConfigMaps and Secrets on a schedule
- **Safe by default**: Starts in dry-run mode to preview deletions before committing changes
- **Configurable**: Select namespaces, exclusion patterns, age thresholds and more
- **Kubernetes-native**: Uses Custom Resources for configuration and status reporting
- **Small footprint**: Minimal resource consumption (64Mi memory, 100m CPU requested)

## Installation

### Prerequisites

- Kubernetes 1.19+
- Helm 3.0+ (for Helm installation method)

### Quick Start - Helm (Recommended)

Install the Cleanup Operator with Helm:

```bash
# Clone the repository
git clone https://github.com/yourusername/cleanup-operator.git
cd cleanup-operator

# Install using Helm
chmod +x install.sh
```

### Manual Installation

If you prefer to deploy without Helm:

```bash
# Apply the manifests
kubectl apply -f deployment.yaml
```

## Configuration

### Helm Chart Values

The operator can be configured by overriding the default values in the Helm chart:

```bash
kubectl apply -f cleanup-crd.yaml
helm install cleanup-operator ./charts/cleanup-operator --set config.dryRun=true,config.cleanupInterval=7200
```

Key configuration parameters:

| Parameter | Description | Default |
|-----------|-------------|---------|
| `config.namespaces` | Namespaces to scan for cleanup | `["default", "production", "staging", "development"]` |
| `config.cleanupInterval` | Interval in seconds between cleanup runs | `3600` |
| `config.unusedThresholdHours` | Minimum age of resources to consider for cleanup | `2` |
| `config.dryRun` | Enable dry-run mode (no actual deletions) | `true` |
| `config.excludePatterns` | Patterns for resources to exclude from cleanup | `["kube-*", "default-token-*"]` |
| `config.logLevel` | Logging level | `"INFO"` |

See [values.yaml](./charts/cleanup-operator/values.yaml) for the complete list of parameters.

### Using Custom Resources

You can also configure the operator through the `Cleanup` Custom Resource:

```yaml
apiVersion: resources.muntashir.com/v1
kind: Cleanup
metadata:
  name: prod-cleanup
  namespace: cleanup-system
spec:
  namespaces:
    - production
    - staging
  unusedThresholdHours: 48
  dryRun: false
```

Apply the Custom Resource:

```bash
kubectl apply -f cleanup-cr.yaml
```

## Usage

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

## How It Works

The Cleanup Operator:

1. **Discovers Resources** - Scans all configmaps and secrets in selected namespaces
2. **Traces References** - Checks if each resource is referenced by any pods, deployments, daemonsets, or statefulsets
3. **Applies Filters** - Excludes resources matching exclusion patterns and those younger than the configured threshold
4. **Performs Cleanup** - Removes unused resources (or logs what would be removed in dry-run mode)

Workload references are tracked through:
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