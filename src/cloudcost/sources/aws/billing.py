import boto3
import pyarrow as pa
import pyarrow.parquet as pq
import io
from typing import Any

from cloudcost.core.registry import registry

@registry.register_source("aws.cost_export")
class AWSCostExportSource:
    def __init__(self, config: dict):
        self.bucket = config.get("bucket")
        self.prefix = config.get("prefix", "")
        self.region = config.get("region", "us-east-1")
        if not self.bucket:
            raise ValueError("aws.cost_export requires 'bucket' in config")
        
        # Boto3 will automatically pick up AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY from env
        self.s3 = boto3.client("s3", region_name=self.region)

    def extract(self, context: Any = None) -> pa.Table:
        # In a real app we would paginate and fetch all matching parquet/csv files.
        # MVP: List objects and download the first parquet file.
        response = self.s3.list_objects_v2(Bucket=self.bucket, Prefix=self.prefix)
        if "Contents" not in response:
            raise ValueError(f"No objects found in s3://{self.bucket}/{self.prefix}")
            
        tables = []
        for obj in response["Contents"]:
            key = obj["Key"]
            if key.endswith(".parquet"):
                # Download to memory
                obj_response = self.s3.get_object(Bucket=self.bucket, Key=key)
                file_stream = io.BytesIO(obj_response["Body"].read())
                tables.append(pq.read_table(file_stream))
                
        if not tables:
            raise ValueError(f"No parquet files found in s3://{self.bucket}/{self.prefix}")
            
        return pa.concat_tables(tables)
