import oss2
import pyarrow as pa
import pyarrow.csv as pv
import io
import os
from typing import Any

from cloudcost.core.registry import registry

@registry.register_source("alibaba.bss_billing")
class AlibabaCostReportSource:
    def __init__(self, config: dict):
        self.endpoint = config.get("endpoint")
        self.bucket_name = config.get("bucket")
        self.prefix = config.get("prefix", "")
        
        if not self.endpoint or not self.bucket_name:
            raise ValueError("alibaba.bss_billing requires 'endpoint' and 'bucket' in config")

        # Get credentials from environment
        access_key_id = os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID")
        access_key_secret = os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET")
        
        if not access_key_id or not access_key_secret:
            raise ValueError("ALIBABA_CLOUD_ACCESS_KEY_ID and ALIBABA_CLOUD_ACCESS_KEY_SECRET environment variables must be set")
            
        auth = oss2.Auth(access_key_id, access_key_secret)
        self.bucket = oss2.Bucket(auth, self.endpoint, self.bucket_name)

    def extract(self, context: Any = None) -> pa.Table:
        tables = []
        for obj in oss2.ObjectIterator(self.bucket, prefix=self.prefix):
            if obj.key.endswith(".csv"):
                result = self.bucket.get_object(obj.key)
                file_stream = io.BytesIO(result.read())
                tables.append(pv.read_csv(file_stream))
                
        if not tables:
            raise ValueError(f"No CSV files found in Alibaba OSS bucket {self.bucket_name}/{self.prefix}")
            
        return pa.concat_tables(tables)
