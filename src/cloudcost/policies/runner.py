import duckdb
from typing import List
from pathlib import Path
from cloudcost.policies.models import Finding
from cloudcost.config.loader import PolicyConfig

class PolicyRunner:
    def __init__(self, db_path: str = "data/cloudcost.duckdb"):
        self.db_path = db_path

    def run_policy(self, policy: PolicyConfig) -> List[Finding]:
        query_file = Path(policy.query_file)
        if not query_file.exists():
            raise FileNotFoundError(f"Policy query file not found: {policy.query_file}")
            
        with open(query_file, "r") as f:
            query = f.read()

        findings = []
        with duckdb.connect(self.db_path, read_only=True) as conn:
            # We assume the query returns specific columns: provider, resource_id, service_name, billed_cost, etc.
            # And we map them to a Finding.
            try:
                result = conn.execute(query).fetchall()
                cols = [desc[0] for desc in conn.description]
                
                for row in result:
                    row_dict = dict(zip(cols, row))
                    
                    evidence = row_dict
                    provider = row_dict.get("provider", "unknown")
                    resource_id = row_dict.get("resource_id", "unknown")
                    service_name = row_dict.get("service_name", "unknown")
                    impact = row_dict.get("billed_cost", 0.0)
                    
                    finding = Finding(
                        policy_name=policy.name,
                        provider=provider,
                        resource_id=resource_id,
                        service_name=service_name,
                        severity=policy.severity,
                        evidence=evidence,
                        estimated_impact=impact,
                        recommended_action=f"Review findings for {policy.name}"
                    )
                    findings.append(finding)
            except Exception as e:
                raise RuntimeError(f"Failed to execute policy '{policy.name}': {e}")
                
        return findings
