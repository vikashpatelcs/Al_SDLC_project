"""
SDLC recommendation, MCDA factors, and customized lifecycle schemas per PS §13-§15.
"""
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class SDLCModelType(str, Enum):
    WATERFALL = "Waterfall"
    V_MODEL = "V-Model"
    SPIRAL = "Spiral"
    AGILE = "Agile"
    DEVSECOPS = "DevSecOps"
    AGILE_V_MODEL = "Agile + V-Model Hybrid"
    AGILE_DEVSECOPS = "Agile + DevSecOps Hybrid"


class SDLCFactor(BaseModel):
    name: str = Field(description="Factor identifier e.g. regulatory_criticality")
    score: int = Field(ge=1, le=5, description="Factor rating on 1-5 Likert scale")
    evidence_quote: str = Field(description="Verbatim statement or requirement excerpt justifying rating")
    user_overridden: bool = Field(default=False, description="True if manually adjusted by stakeholder")


class SDLCPhaseWorkflow(BaseModel):
    phase_name: str = Field(description="e.g. Inception & Scope, Architecture & Design, Implementation")
    activity: str = Field(description="Primary engineering activities")
    role: str = Field(description="Responsible role")
    deliverable: str = Field(description="Concrete deliverable")
    security_activity: str = Field(description="Mandatory security task e.g. Threat modeling, SAST/DAST")
    testing: str = Field(description="Quality assurance verification")
    compliance_checkpoint: str = Field(description="Mandatory regulatory audit / RBI verification")
    human_approval: str = Field(description="Required human gate sign-off")
    entry_criteria: str = Field(description="Prerequisites before starting phase")
    exit_criteria: str = Field(description="Definition of done for phase exit")
    traceability_requirement: str = Field(description="RTM bidirectional linkage required")


class ModelScoreRanking(BaseModel):
    model_type: SDLCModelType = Field(description="Evaluated SDLC methodology")
    score_percentage: float = Field(ge=0.0, le=100.0, description="Normalized compatibility percentage")
    rank: int = Field(ge=1, description="Ranking position (1=top recommended)")
    key_strengths: List[str] = Field(default_factory=list, description="Top positive alignment reasons")
    tradeoffs: List[str] = Field(default_factory=list, description="Risks or frictions associated with model")


class SDLCRecommendation(BaseModel):
    chat_id: Optional[str] = Field(default=None, description="Linked chat session ID")
    selected_model: SDLCModelType = Field(description="Top recommended methodology")
    rankings: List[ModelScoreRanking] = Field(description="Ranked scores across all 7 methodologies")
    factor_evaluations: Dict[str, SDLCFactor] = Field(description="Ratings for all 13 PS §13 factors")
    explanation: str = Field(description="LLM explanation synthesizing MCDA weights and evidence")
    workflow: List[SDLCPhaseWorkflow] = Field(
        default_factory=list,
        description="Customized phase-by-phase lifecycle workflow (10 dimensions per phase)"
    )
    is_approved: bool = Field(default=False, description="Whether 4-role sign-off has been achieved")
