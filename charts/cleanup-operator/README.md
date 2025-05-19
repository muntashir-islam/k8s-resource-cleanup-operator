# Cleanup Operator Helm Chart

A Helm chart for the Kubernetes Cleanup Operator, which automates the detection and removal of unused ConfigMaps and Secrets.

## Introduction

The Cleanup Operator is designed to help maintain a clean Kubernetes environment by identifying and removing ConfigMaps and Secrets that are no longer referenced by any workloads. This reduces cluster clutter and can help with resource management.

## Prerequisites

- Kubernetes 1.19+
- Helm 3.0+

## Installing the Chart

To install the chart with the release name `cleanup-operator`:

```bash
helm install cleanup-operator ./cleanup-operator
```

## Uninstalling the Chart

To uninstall/delete the `cleanup-operator` deployment:

```bash
helm uninstall cleanup-operator
```

## Configuration

The following table lists the configurable parameters of the Cleanup Operator chart and their default values.

| Parameter | Description | Default |
|-----------|-------------|---------|
| `image.repository` | Operator container image repository | `muntashir/cleanup-operator` |
| `image.tag` | Operator container image tag | `v4` |
| `image.pullPolicy` | Operator container image pull policy | `IfNotPresent` |
| `resources.limits.cpu` | CPU resource limits | `500m` |
| `resources.limits.memory` | Memory resource limits | `256Mi` |
| `resources.requests.cpu` | CPU resource requests | `100m` |
| `resources.requests.memory` | Memory resource requests | `64Mi` |
| `config.namespaces` | List of namespaces to scan for cleanup | `[default, production, staging, development]` |
| `config.cleanupInterval` | Interval in seconds between cleanup runs | `3600` |
| `config.unusedThresholdHours` | Minimum age (in hours) of resources to consider for cleanup | `2` |
| `config.dryRun` | Enable dry-run mode (no actual deletions) | `true` |
| `config.excludePatterns` | Patterns for resources to exclude from cleanup | `[kube-*, default-token-*]` |
| `config.logLevel` | Logging level | `INFO` |
| `deployment.replicas` | Number of operator replicas | `1` |
| `serviceAccount.create` | Create a service account | `true` |
| `serviceAccount.name` | Service account name | `cleanup-operator` |
| `rbac.create` | Create RBAC resources | `true` |
| `podDisruptionBudget.enabled` | Enable PodDisruptionBudget | `true` |
| `podDisruptionBudget.minAvailable` | Minimum available pods | `0` |
| `defaultCleanupCR.create` | Create a default Cleanup CR | `true` |
| `defaultCleanupCR.name` | Name of the default Cleanup CR | `default-cleanup` |
| `defaultCleanupCR.spec` | Specification for the default Cleanup CR | See values.yaml |

## Using the Cleanup Operator

### Custom Resource Definition (CRD)

The operator introduces a Custom Resource Definition (CRD) called `Cleanup`:

```yaml
apiVersion: resources.muntashir.com/v1
kind: Cleanup
metadata:
  name: my-cleanup
  namespace: cleanup-system
spec:
  namespaces:
    - default
    - production
  unusedThresholdHours: 24
  dryRun: false
```

### Triggering a Cleanup

You can trigger a cleanup manually by adding an annotation to your Cleanup CR:

```bash
kubectl annotate cleanup default-cleanup -n cleanup-system cleanup.operator/trigger=now
```

Or by setting the `force` field in the spec:

```yaml
apiVersion: resources.muntashir.com/v1
kind: Cleanup
metadata:
  name: my-cleanup
  namespace: cleanup-system
spec:
  force: true
```

### Monitoring Cleanup Results

You can check the status of a cleanup operation:

```bash
kubectl get cleanup default-cleanup -n cleanup-system -o yaml
```

Look for the `status` field which contains details about the last cleanup operation.

## Customizing the Operator

### Image

To use a custom operator image, modify the `image` section in your values:

```yaml
image:
  repository: your-registry/cleanup-operator
  tag: your-tag
```

### Configuration

You can customize the operator behavior by modifying the `config` section in your values. For example, to change the namespaces that are scanned and increase the minimum age threshold:

```yaml
config:
  namespaces:
    - default
    - kube-public
  unusedThresholdHours: 48
```

### Dry Run Mode

It's recommended to start with dry-run mode enabled (`dryRun: true`) to see what would be deleted without actually removing anything. After reviewing the logs and confirming the behavior, you can disable dry-run mode:

```yaml
config:
  dryRun: false
```