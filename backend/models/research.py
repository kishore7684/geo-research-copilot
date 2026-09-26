# backend/models/research.py
from sqlmodel import SQLModel, Field
from typing import Optional, List
from datetime import datetime
import json

class ResearchOption(SQLModel):
    id: str                          # e.g. "diff_exp", "pathway", "clustering"
    title: str
    question: str                    # the biological question it answers
    required_data: List[str]         # what data types are needed
    expected_outputs: List[str]      # what this analysis produces
    feasible: bool                   # does this dataset actually support it
    feasibility_reason: str          # why feasible or not
    difficulty: str                  # "beginner", "intermediate", "advanced"

class ResearchPlan(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    accession: str
    options_json: str                # JSON list of ResearchOption
    created_at: datetime = Field(default_factory=datetime.utcnow)
