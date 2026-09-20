import pyarrow as pa
from typing import Any
from google.cloud import bigquery

from cloudcost.core.registry import registry

@registry.register_destination("bigquery")
class BigQueryDestination:
    def __init__(self, config: dict):
        self.project = config.get("project")
        self.dataset = config.get("dataset")
        
        # We rely on google-auth default credentials
        self.client = bigquery.Client(project=self.project) if self.project else bigquery.Client()

    def load(self, table: pa.Table, target: Any, context: Any = None) -> None:
        table_name = target.table if hasattr(target, "table") and target.table else "default_table"
        mode = target.mode if hasattr(target, "mode") and target.mode else "overwrite"
        
        # Build the full table ID
        if self.dataset:
            table_id = f"{self.client.project}.{self.dataset}.{table_name}"
        else:
            table_id = table_name

        job_config = bigquery.LoadJobConfig()
        
        if mode == "overwrite":
            job_config.write_disposition = bigquery.WriteDisposition.WRITE_TRUNCATE
        else:
            # For "append" and "merge" MVP fallback to APPEND
            job_config.write_disposition = bigquery.WriteDisposition.WRITE_APPEND
            
        # Write the pyarrow table directly to BigQuery via the client!
        job = self.client.load_table_from_dataframe(
            table.to_pandas(), 
            table_id, 
            job_config=job_config
        )
        
        # Wait for the load job to complete
        job.result()
