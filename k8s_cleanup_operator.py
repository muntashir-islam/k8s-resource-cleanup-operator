#!/usr/bin/env python3

import asyncio
import logging
import kopf
import kubernetes
import yaml
from datetime import datetime, timedelta, timezone
from typing import Set, List, Dict, Any, Optional
from kubernetes.client.rest import ApiException

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global configuration
CONFIG = {
    'namespaces': ['default'],
    'cleanup_interval': 3600,
    'unused_threshold_hours': 1,
    'dry_run': False,
    'exclude_patterns': [
        'kube-*',  # System configmaps
        'default-token-*',  # Service account tokens
    ]
}


def load_config():
    """Load configuration from ConfigMap or environment variables."""
    try:
        # Try to load from Kubernetes ConfigMap
        kubernetes.config.load_incluster_config()
        v1 = kubernetes.client.CoreV1Api()
        
        try:
            config_map = v1.read_namespaced_config_map(
                name='cleanup-operator-config',
                namespace='cleanup-system'
            )
            if 'config.yaml' in config_map.data:
                config_data = yaml.safe_load(config_map.data['config.yaml'])
                CONFIG.update(config_data)
                logger.info("Configuration loaded from ConfigMap")
        except ApiException:
            logger.info("ConfigMap not found, using environment variables")
            
        # Override with environment variables if present
        import os
        if 'CLEANUP_NAMESPACES' in os.environ:
            CONFIG['namespaces'] = [ns.strip() for ns in os.environ['CLEANUP_NAMESPACES'].split(',')]
        if 'CLEANUP_INTERVAL' in os.environ:
            CONFIG['cleanup_interval'] = int(os.environ['CLEANUP_INTERVAL'])
        if 'DRY_RUN' in os.environ:
            CONFIG['dry_run'] = os.environ['DRY_RUN'].lower() == 'true'
            
    except Exception as e:
        logger.warning(f"Failed to load config from cluster, using defaults: {e}")


class ResourceCleanup:
    """Handles cleanup logic for secrets and configmaps."""
    
    def __init__(self):
        self.v1 = kubernetes.client.CoreV1Api()
        self.apps_v1 = kubernetes.client.AppsV1Api()
    
    def get_resource_references(self, namespace: str) -> Dict[str, Set[str]]:
        """Get all secret and configmap references from workloads."""
        references = {'secrets': set(), 'configmaps': set()}
        
        try:
            # Get references from pods
            pods = self.v1.list_namespaced_pod(namespace=namespace)
            for pod in pods.items:
                self._extract_references_from_pod_spec(pod.spec, references)
            
            # Get references from deployments
            deployments = self.apps_v1.list_namespaced_deployment(namespace=namespace)
            for deployment in deployments.items:
                if deployment.spec.template.spec:
                    self._extract_references_from_pod_spec(deployment.spec.template.spec, references)
            
            # Get references from daemonsets
            daemonsets = self.apps_v1.list_namespaced_daemon_set(namespace=namespace)
            for daemonset in daemonsets.items:
                if daemonset.spec.template.spec:
                    self._extract_references_from_pod_spec(daemonset.spec.template.spec, references)
            
            # Get references from statefulsets
            statefulsets = self.apps_v1.list_namespaced_stateful_set(namespace=namespace)
            for statefulset in statefulsets.items:
                if statefulset.spec.template.spec:
                    self._extract_references_from_pod_spec(statefulset.spec.template.spec, references)
                    
        except ApiException as e:
            logger.error(f"Error getting resource references for namespace {namespace}: {e}")
            
        return references
    
    def _extract_references_from_pod_spec(self, pod_spec, references: Dict[str, Set[str]]):
        """Extract secret and configmap references from a pod specification."""
        if not pod_spec:
            return
            
        # Check volumes
        if pod_spec.volumes:
            for volume in pod_spec.volumes:
                if volume.secret:
                    references['secrets'].add(volume.secret.secret_name)
                if volume.config_map:
                    references['configmaps'].add(volume.config_map.name)
                if volume.projected:
                    # Handle projected volumes
                    for source in volume.projected.sources or []:
                        if source.secret:
                            references['secrets'].add(source.secret.name)
                        if source.config_map:
                            references['configmaps'].add(source.config_map.name)
        
        # Check containers and init containers
        all_containers = []
        if pod_spec.containers:
            all_containers.extend(pod_spec.containers)
        if pod_spec.init_containers:
            all_containers.extend(pod_spec.init_containers)
        if pod_spec.ephemeral_containers:
            all_containers.extend(pod_spec.ephemeral_containers)
        
        for container in all_containers:
            # Check environment variables
            if container.env:
                for env_var in container.env:
                    if env_var.value_from:
                        if env_var.value_from.secret_key_ref:
                            references['secrets'].add(env_var.value_from.secret_key_ref.name)
                        if env_var.value_from.config_map_key_ref:
                            references['configmaps'].add(env_var.value_from.config_map_key_ref.name)
            
            # Check environment from
            if container.env_from:
                for env_from in container.env_from:
                    if env_from.secret_ref:
                        references['secrets'].add(env_from.secret_ref.name)
                    if env_from.config_map_ref:
                        references['configmaps'].add(env_from.config_map_ref.name)
        
        # Check image pull secrets
        if pod_spec.image_pull_secrets:
            for secret_ref in pod_spec.image_pull_secrets:
                references['secrets'].add(secret_ref.name)
        
        # Check service account
        if pod_spec.service_account_name:
            # Service accounts typically have associated secrets
            try:
                sa = self.v1.read_namespaced_service_account(
                    name=pod_spec.service_account_name,
                    namespace=pod_spec.namespace or 'default'
                )
                if sa.secrets:
                    for secret_ref in sa.secrets:
                        references['secrets'].add(secret_ref.name)
                if sa.image_pull_secrets:
                    for secret_ref in sa.image_pull_secrets:
                        references['secrets'].add(secret_ref.name)
            except ApiException:
                pass  # Service account might not exist or we might not have permissions
    
    def should_exclude_resource(self, name: str, resource_type: str) -> bool:
        """Check if a resource should be excluded from cleanup."""
        import fnmatch
        
        for pattern in CONFIG['exclude_patterns']:
            if fnmatch.fnmatch(name, pattern):
                return True
        
        # Additional type-specific exclusions
        if resource_type == 'secret':
            # Exclude service account tokens and docker config secrets
            if name.startswith('default-token-') or name.endswith('-token'):
                return True
        
        return False
    
    def get_unused_resources(self, namespace: str) -> Dict[str, List[str]]:
        """Get lists of unused secrets and configmaps."""
        unused = {'secrets': [], 'configmaps': []}
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=CONFIG['unused_threshold_hours'])
        
        # Get all resource references
        references = self.get_resource_references(namespace)
        
        try:
            # Check secrets
            secrets = self.v1.list_namespaced_secret(namespace=namespace)
            for secret in secrets.items:
                if self.should_exclude_resource(secret.metadata.name, 'secret'):
                    continue
                
                # Skip system secrets by type
                if secret.type in [
                    'kubernetes.io/service-account-token',
                    'kubernetes.io/dockercfg',
                    'kubernetes.io/dockerconfigjson'
                ]:
                    continue
                
                if (secret.metadata.name not in references['secrets'] and 
                    secret.metadata.creation_timestamp.replace(tzinfo=timezone.utc) < cutoff_time):
                    unused['secrets'].append(secret.metadata.name)
            
            # Check configmaps
            configmaps = self.v1.list_namespaced_config_map(namespace=namespace)
            for configmap in configmaps.items:
                if self.should_exclude_resource(configmap.metadata.name, 'configmap'):
                    continue
                
                if (configmap.metadata.name not in references['configmaps'] and 
                    configmap.metadata.creation_timestamp.replace(tzinfo=timezone.utc) < cutoff_time):
                    unused['configmaps'].append(configmap.metadata.name)
                    
        except ApiException as e:
            logger.error(f"Error getting unused resources for namespace {namespace}: {e}")
        
        return unused
    
    def cleanup_namespace(self, namespace: str) -> Dict[str, int]:
        """Clean up unused resources in a namespace."""
        logger.info(f"Starting cleanup for namespace: {namespace}")
        
        unused_resources = self.get_unused_resources(namespace)
        results = {'secrets_deleted': 0, 'configmaps_deleted': 0}
        
        # Delete unused secrets
        for secret_name in unused_resources['secrets']:
            try:
                if CONFIG['dry_run']:
                    logger.info(f"[DRY RUN] Would delete unused secret: {namespace}/{secret_name}")
                else:
                    self.v1.delete_namespaced_secret(name=secret_name, namespace=namespace)
                    logger.info(f"Deleted unused secret: {namespace}/{secret_name}")
                results['secrets_deleted'] += 1
            except ApiException as e:
                logger.error(f"Failed to delete secret {namespace}/{secret_name}: {e}")
        
        # Delete unused configmaps
        for configmap_name in unused_resources['configmaps']:
            try:
                if CONFIG['dry_run']:
                    logger.info(f"[DRY RUN] Would delete unused configmap: {namespace}/{configmap_name}")
                else:
                    self.v1.delete_namespaced_config_map(name=configmap_name, namespace=namespace)
                    logger.info(f"Deleted unused configmap: {namespace}/{configmap_name}")
                results['configmaps_deleted'] += 1
            except ApiException as e:
                logger.error(f"Failed to delete configmap {namespace}/{configmap_name}: {e}")
        
        logger.info(f"Cleanup completed for namespace {namespace}: "
                   f"deleted {results['secrets_deleted']} secrets, "
                   f"{results['configmaps_deleted']} configmaps")
        
        return results


# Global cleanup instance
cleanup_handler = None


@kopf.on.startup()
async def startup_handler(settings: kopf.OperatorSettings, **kwargs):
    """Initialize the operator on startup."""
    global cleanup_handler
    
    # Configure kopf settings
    settings.posting.level = logging.WARNING  # Reduce event posting noise
    settings.watching.connect_timeout = 60
    settings.watching.server_timeout = 600
    
    # Load configuration
    load_config()
    logger.info(f"Operator starting with config: {CONFIG}")
    
    # Initialize cleanup handler
    cleanup_handler = ResourceCleanup()
    
    logger.info("Cleanup operator started successfully")


# Create handler for our CRD
@kopf.on.create('cleanups.resources.muntashir.com', 'v1')
async def create_fn(spec, **kwargs):
    """Handle the creation of a Cleanup CR."""
    logger.info(f"Cleanup CR created with spec: {spec}")
    await perform_cleanup()
    return {"status": "Cleanup triggered manually"}


# Timer that runs periodically
@kopf.timer('cleanups.resources.muntashir.com', 'v1', interval=CONFIG['cleanup_interval'])
async def cleanup_timer(**kwargs):
    """Timer-based cleanup across all configured namespaces."""
    logger.info("Timer-triggered cleanup starting")
    await perform_cleanup()


async def perform_cleanup():
    """Perform cleanup across all configured namespaces."""
    if not cleanup_handler:
        logger.warning("Cleanup handler not initialized")
        return
    
    logger.info("Starting scheduled cleanup cycle")
    total_results = {'secrets_deleted': 0, 'configmaps_deleted': 0}
    
    for namespace in CONFIG['namespaces']:
        try:
            results = cleanup_handler.cleanup_namespace(namespace)
            total_results['secrets_deleted'] += results['secrets_deleted']
            total_results['configmaps_deleted'] += results['configmaps_deleted']
        except Exception as e:
            logger.error(f"Error cleaning up namespace {namespace}: {e}")
    
    logger.info(f"Cleanup cycle completed. Total: "
               f"{total_results['secrets_deleted']} secrets, "
               f"{total_results['configmaps_deleted']} configmaps deleted")


@kopf.on.event('', 'v1', 'configmaps', field='metadata.name', value='cleanup-operator-config')
async def config_change_handler(event, **kwargs):
    """Handle configuration changes."""
    if event['type'] in ['ADDED', 'MODIFIED']:
        logger.info("Configuration changed, reloading...")
        load_config()
        logger.info(f"New configuration: {CONFIG}")


# Manual trigger via annotation
@kopf.on.update('', 'v1', 'configmaps', field='metadata.name', value='cleanup-operator-config')
async def manual_trigger_handler(old, new, **kwargs):
    """Trigger manual cleanup via ConfigMap annotation."""
    annotations = new.get('metadata', {}).get('annotations', {})
    if annotations.get('cleanup.operator/trigger') == 'now':
        logger.info("Manual cleanup triggered via annotation")
        await perform_cleanup()
        
        # Remove the trigger annotation to prevent duplicate runs
        try:
            v1 = kubernetes.client.CoreV1Api()
            config_map = v1.read_namespaced_config_map(
                name='cleanup-operator-config',
                namespace='cleanup-system'
            )
            if config_map.metadata.annotations:
                config_map.metadata.annotations.pop('cleanup.operator/trigger', None)
                v1.patch_namespaced_config_map(
                    name='cleanup-operator-config',
                    namespace='cleanup-system',
                    body=config_map
                )
        except Exception as e:
            logger.error(f"Failed to remove trigger annotation: {e}")


if __name__ == '__main__':
    # Initialize Kubernetes client
    try:
        kubernetes.config.load_incluster_config()
    except kubernetes.config.ConfigException:
        kubernetes.config.load_kube_config()
    
    # Run the operator
    kopf.run()