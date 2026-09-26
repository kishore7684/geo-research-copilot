# backend/models/dataset.py

from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
import json

class DatasetBase(SQLModel):
    accession: str
    source: str  # GEO, PubMed, SRA
    title: Optional[str] = None
    organism: Optional[str] = None
    technology: Optional[str] = None
    sample_count: Optional[int] = None
    raw_metadata: Optional[str] = None   # JSON string
    llm_summary: Optional[str] = None    # JSON string

class Dataset(DatasetBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class DatasetCreate(DatasetBase):
    pass

class DatasetRead(DatasetBase):
    id: int
    created_at: datetime
