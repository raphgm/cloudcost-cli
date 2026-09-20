import os
import re
import yaml
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class SourceConfig(BaseModel):
    name: str
    type: str
    config: Dict[str, Any]
    credentials: Optional[str] = None

class TransformConfig(BaseModel):
    name: str
    type: str
    input: Optional[str] = None
    inputs: Optional[List[str]] = None
    config: Optional[Dict[str, Any]] = None

class DestinationConfig(BaseModel):
    name: str
    type: str
    config: Dict[str, Any]

class LoadConfig(BaseModel):
    input: str
    destination: str
    table: Optional[str] = None
    path: Optional[str] = None
    mode: str
    keys: Optional[List[str]] = None

class PolicyConfig(BaseModel):
    name: str
    type: str
    query_file: str
    severity: str
    input: Optional[str] = None

class ObservabilityConfig(BaseModel):
    log_level: str = "info"
    emit_run_summary: bool = True
    metrics: bool = False

class PipelineMeta(BaseModel):
    name: str
    mode: str
    timezone: str = "UTC"
    failure_policy: str = "fail_fast"

class PipelineConfig(BaseModel):
    version: str
    pipeline: PipelineMeta
    sources: List[SourceConfig]
    transforms: List[TransformConfig] = Field(default_factory=list)
    destinations: List[DestinationConfig]
    loads: List[LoadConfig]
    policies: List[PolicyConfig] = Field(default_factory=list)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)

def _interpolate_env_vars(data: Any) -> Any:
    """Recursively replace ${VAR} with os.environ.get('VAR') in strings."""
    if isinstance(data, dict):
        return {k: _interpolate_env_vars(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_interpolate_env_vars(item) for item in data]
    elif isinstance(data, str):
        pattern = re.compile(r'\$\{([^}]+)\}')
        def replace(match):
            var_name = match.group(1)
            return os.environ.get(var_name, f"${{{var_name}}}")
        return pattern.sub(replace, data)
    return data

def load_config(file_path: str) -> PipelineConfig:
    with open(file_path, "r") as f:
        raw_data = yaml.safe_load(f)
    
    interpolated_data = _interpolate_env_vars(raw_data)
    return PipelineConfig(**interpolated_data)
