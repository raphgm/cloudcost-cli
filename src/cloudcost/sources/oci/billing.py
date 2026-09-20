import oci
import pyarrow as pa
import pyarrow.csv as pv
import io
from typing import Any

from cloudcost.core.registry import registry

@registry.register_source("oci.cost_report")
class OCICostReportSource:
    def __init__(self, config: dict):
        self.namespace = config.get("namespace")
        self.bucket = config.get("bucket")
        self.prefix = config.get("prefix", "")
        
        if not self.namespace or not self.bucket:
            raise ValueError("oci.cost_report requires 'namespace' and 'bucket' in config")

        # Uses default ~/.oci/config profile or instance principals
        self.config = oci.config.from_file()
        self.object_storage_client = oci.object_storage.ObjectStorageClient(self.config)

    def extract(self, context: Any = None) -> pa.Table:
        list_objects_response = self.object_storage_client.list_objects(
            self.namespace,
            self.bucket,
            prefix=self.prefix
        )
        
        tables = []
        for obj in list_objects_response.data.objects:
            if obj.name.endswith(".csv"):
                get_obj_response = self.object_storage_client.get_object(
                    self.namespace,
                    self.bucket,
                    obj.name
                )
                file_stream = io.BytesIO(get_obj_response.data.content)
                tables.append(pv.read_csv(file_stream))
                
        if not tables:
            raise ValueError(f"No CSV files found in OCI bucket {self.bucket}/{self.prefix}")
            
        return pa.concat_tables(tables)
