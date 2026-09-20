import boto3
import pyarrow as pa
from typing import Any

from cloudcost.core.registry import registry

@registry.register_source("aws.resource_inventory")
class AWSResourceInventorySource:
    def __init__(self, config: dict):
        self.regions = config.get("regions", ["us-east-1"])
        
    def extract(self, context: Any = None) -> pa.Table:
        resources = []
        
        for region in self.regions:
            # We use resourcegroupstaggingapi to pull all tagged resources across the region
            client = boto3.client("resourcegroupstaggingapi", region_name=region)
            paginator = client.get_paginator("get_resources")
            
            for page in paginator.paginate():
                for resource in page["ResourceTagMappingList"]:
                    arn = resource["ResourceARN"]
                    tags = {t["Key"]: t["Value"] for t in resource.get("Tags", [])}
                    
                    resources.append({
                        "provider": "aws",
                        "resource_id": arn,
                        "region": region,
                        "owner": tags.get("Owner", "unknown"),
                        "environment": tags.get("Environment", "unknown")
                    })
        
        if not resources:
            # Return empty schema if no resources found
            schema = pa.schema([
                ("provider", pa.string()),
                ("resource_id", pa.string()),
                ("region", pa.string()),
                ("owner", pa.string()),
                ("environment", pa.string())
            ])
            return pa.Table.from_arrays([[]]*5, schema=schema)
            
        # Convert list of dicts to PyArrow Table
        provider_arr = pa.array([r["provider"] for r in resources])
        resource_id_arr = pa.array([r["resource_id"] for r in resources])
        region_arr = pa.array([r["region"] for r in resources])
        owner_arr = pa.array([r["owner"] for r in resources])
        env_arr = pa.array([r["environment"] for r in resources])
        
        return pa.Table.from_arrays(
            [provider_arr, resource_id_arr, region_arr, owner_arr, env_arr],
            names=["provider", "resource_id", "region", "owner", "environment"]
        )
