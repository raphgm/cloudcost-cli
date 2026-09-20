import pyarrow as pa
import pyarrow.csv as pv
import io
from typing import Any
from azure.storage.blob import BlobServiceClient
from azure.identity import DefaultAzureCredential

from cloudcost.core.registry import registry

@registry.register_source("azure.cost_export")
class AzureCostExportSource:
    def __init__(self, config: dict):
        self.account_url = config.get("account_url")
        self.container = config.get("container")
        self.prefix = config.get("prefix", "")
        
        if not self.account_url or not self.container:
            raise ValueError("azure.cost_export requires 'account_url' and 'container' in config")

        # Uses environment variables (AZURE_CLIENT_ID, etc.) or Managed Identity
        credential = DefaultAzureCredential()
        self.blob_service_client = BlobServiceClient(account_url=self.account_url, credential=credential)

    def extract(self, context: Any = None) -> pa.Table:
        container_client = self.blob_service_client.get_container_client(self.container)
        blob_list = container_client.list_blobs(name_starts_with=self.prefix)
        
        tables = []
        for blob in blob_list:
            if blob.name.endswith(".csv"):
                blob_client = container_client.get_blob_client(blob)
                download_stream = blob_client.download_blob()
                file_stream = io.BytesIO(download_stream.readall())
                tables.append(pv.read_csv(file_stream))
                
        if not tables:
            raise ValueError(f"No CSV files found in {self.container}/{self.prefix}")
            
        return pa.concat_tables(tables)
