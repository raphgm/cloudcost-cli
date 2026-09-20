from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
import uuid
import datetime

class Finding(BaseModel):
    finding_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_name: str
    provider: str
    resource_id: Optional[str] = None
    service_name: Optional[str] = None
    severity: str
    status: str = "open"
    detected_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    evidence: Dict[str, Any]
    estimated_impact: Optional[float] = None
    recommended_action: str
