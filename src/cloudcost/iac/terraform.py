import json
from typing import List, Dict, Any

class TerraformMapper:
    def __init__(self, state_path: str):
        self.state_path = state_path

    def load_state(self) -> Dict[str, Any]:
        with open(self.state_path, "r") as f:
            return json.load(f)

    def extract_resources(self) -> List[Dict[str, str]]:
        state = self.load_state()
        mapped_resources = []
        
        for resource in state.get("resources", []):
            module = resource.get("module", "root")
            resource_type = resource.get("type", "unknown")
            resource_name = resource.get("name", "unknown")
            
            for instance in resource.get("instances", []):
                attrs = instance.get("attributes", {})
                # For AWS, id or arn usually works. We'll grab id/arn if available.
                cloud_id = attrs.get("arn") or attrs.get("id")
                
                if cloud_id:
                    mapped_resources.append({
                        "terraform_address": f"{module}.{resource_type}.{resource_name}",
                        "cloud_id": cloud_id,
                        "provider": resource.get("provider", "unknown").split("/")[-1].replace('"', '')
                    })
                    
        return mapped_resources

    def map_findings(self, findings_path: str) -> List[Dict[str, Any]]:
        mapped_resources = self.extract_resources()
        
        # Build index by cloud_id
        tf_index = {res["cloud_id"]: res["terraform_address"] for res in mapped_resources}
        
        with open(findings_path, "r") as f:
            findings = json.load(f)
            
        mapped_findings = []
        for finding in findings:
            res_id = finding.get("resource_id")
            if res_id and res_id in tf_index:
                finding["terraform_address"] = tf_index[res_id]
                finding["mapping_confidence"] = "exact_state_id"
                mapped_findings.append(finding)
                
        return mapped_findings
