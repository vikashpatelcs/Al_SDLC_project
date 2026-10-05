"""
Risk register and threat modeling schemas per PS §11, §12 and Master Plan Phase 10.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, model_validator


class RiskCategory(str, Enum):
    BUSINESS = "business"
    TECHNICAL = "technical"
    SECURITY = "security"
    COMPLIANCE = "compliance"
    OPERATIONAL = "operational"
    AVAILABILITY = "availability"
    LEGACY = "legacy"


class RiskSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskStatus(str, Enum):
    IDENTIFIED = "identified"
    ANALYZED = "analyzed"
    MITIGATED = "mitigated"
    ACCEPTED = "accepted"
    ESCALATED = "escalated"


class RiskItem(BaseModel):
    id: str = Field(description="Unique risk identifier e.g. RSK-001")
    project_id: Optional[str] = Field(default=None, description="Linked project or chat ID")
    requirement_id: Optional[str] = Field(default=None, description="Linked requirement if risk is requirement-specific")
    title: str = Field(description="Brief threat or risk description")
    category: RiskCategory = Field(description="Risk taxonomy category")
    probability: int = Field(ge=1, le=5, description="Probability score (1=Rare to 5=Almost Certain)")
    impact: int = Field(ge=1, le=5, description="Impact score (1=Negligible to 5=Catastrophic)")
    risk_score: int = Field(default=1, ge=1, le=25, description="Composite score = probability * impact")
    severity: RiskSeverity = Field(default=RiskSeverity.LOW, description="Calculated 5x5 severity tier")
    mitigation: str = Field(description="Concrete operational, security, or architectural control")
    owner: str = Field(default="Compliance & Risk Team", description="Designated role responsible for monitoring")
    status: RiskStatus = Field(default=RiskStatus.IDENTIFIED, description="Current tracking status")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def compute_risk_metrics(self) -> "RiskItem":
        # Calculate risk score
        score = self.probability * self.impact
        self.risk_score = score
        # Classify severity
        if score >= 16:
            self.severity = RiskSeverity.CRITICAL
        elif score >= 10:
            self.severity = RiskSeverity.HIGH
        elif score >= 5:
            self.severity = RiskSeverity.MEDIUM
        else:
            self.severity = RiskSeverity.LOW
        return self
