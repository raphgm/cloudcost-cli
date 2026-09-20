from typing import Dict, List, Optional
from pydantic import BaseModel

class ProviderCapabilities(BaseModel):
    provider: str
    billing_export: bool = False
    billing_api: bool = False
    resource_inventory: bool = False
    utilization_metrics: bool = False
    commitment_recommendations: bool = False
    native_optimization_api: bool = False

class CapabilityRegistry:
    def __init__(self):
        self.providers: Dict[str, ProviderCapabilities] = {}

    def register(self, capabilities: ProviderCapabilities):
        self.providers[capabilities.provider] = capabilities

    def list_providers(self) -> List[str]:
        return list(self.providers.keys())

    def get_capabilities(self, provider: str) -> Optional[ProviderCapabilities]:
        return self.providers.get(provider)

capabilities_registry = CapabilityRegistry()

# Register AWS capabilities
capabilities_registry.register(ProviderCapabilities(
    provider="aws",
    billing_export=True,
    billing_api=True,
    resource_inventory=True,
    utilization_metrics=True,
    commitment_recommendations=True,
    native_optimization_api=True
))

# Register Azure capabilities
capabilities_registry.register(ProviderCapabilities(
    provider="azure",
    billing_export=True,
    billing_api=True,
    resource_inventory=True,
    utilization_metrics=True,
    commitment_recommendations=True,
    native_optimization_api=True
))

# Register OCI capabilities
capabilities_registry.register(ProviderCapabilities(
    provider="oci",
    billing_export=True,
    resource_inventory=True,
    utilization_metrics=True
))

# Register Alibaba capabilities
capabilities_registry.register(ProviderCapabilities(
    provider="alibaba",
    billing_export=True,
    resource_inventory=True
))
