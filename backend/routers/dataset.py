# backend/routers/dataset.py

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from backend.database import get_session
from backend.models.dataset import Dataset, DatasetRead
from backend.services.geo_service import detect_source, fetch_geo_metadata
from backend.services.llm_service import summarize_dataset
from pydantic import BaseModel
import json

router = APIRouter(prefix="/api/dataset", tags=["dataset"])

class AnalyzeRequest(BaseModel):
    url: str

@router.post("/analyze")
def analyze_dataset(request: AnalyzeRequest, session: Session = Depends(get_session)):

    # Step 1: detect source
    detected = detect_source(request.url)

    if detected["source"] == "unknown":
        raise HTTPException(status_code=400, detail="Could not detect dataset source. Paste a GEO accession like GSE99884.")

    if detected["source"] != "GEO":
        raise HTTPException(status_code=400, detail=f"{detected['source']} support coming soon. Use GEO for now.")

    accession = detected["accession"]

    # Step 2: check if already in DB
    existing = session.exec(
        select(Dataset).where(Dataset.accession == accession)
    ).first()

    if existing:
        return {
            "status": "cached",
            "accession": accession,
            "metadata": json.loads(existing.raw_metadata),
            "summary": json.loads(existing.llm_summary) if existing.llm_summary else None
        }

    # Step 3: fetch real metadata from GEO
    metadata = fetch_geo_metadata(accession)

    if "error" in metadata:
        raise HTTPException(status_code=404, detail=metadata["error"])

    # Step 4: LLM summarizes it
    summary = summarize_dataset(metadata)

    # Step 5: store in DB
    dataset = Dataset(
        accession=accession,
        source="GEO",
        title=metadata.get("title"),
        organism=metadata.get("organism"),
        technology=metadata.get("technology"),
        sample_count=metadata.get("sample_count"),
        raw_metadata=json.dumps(metadata),
        llm_summary=json.dumps(summary)
    )
    session.add(dataset)
    session.commit()
    session.refresh(dataset)

    return {
        "status": "analyzed",
        "accession": accession,
        "metadata": metadata,
        "summary": summary
    }


@router.get("/{accession}")
def get_dataset(accession: str, session: Session = Depends(get_session)):
    dataset = session.exec(
        select(Dataset).where(Dataset.accession == accession.upper())
    ).first()

    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found. Analyze it first.")

    return {
        "accession": dataset.accession,
        "metadata": json.loads(dataset.raw_metadata),
        "summary": json.loads(dataset.llm_summary) if dataset.llm_summary else None,
        "created_at": dataset.created_at
    }
