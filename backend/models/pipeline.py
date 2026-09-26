# backend/models/pipeline.py

from sqlmodel import SQLModel, Field
from typing import Optional, List
from datetime import datetime

class PipelineStep(SQLModel):
    step_id: int
    name: str
    tool: str
    why: str
    input: str
    output: str
    decision_point: bool = False
    decision_logic: Optional[str] = None
    estimated_time: Optional[str] = None

class PipelinePlan(SQLModel):
    research_question: str
    hypothesis: str
    analysis_type: str
    dataset_accession: str
    steps: List[PipelineStep]
    expected_outputs: List[str]
    provenance: dict

class PipelinePlanDB(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    accession: str
    analysis_id: str
    plan_json: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
