# backend/routers/research.py

from fastapi import APIRouter, HTTPException
from backend.services.geo_service import fetch_geo_metadata
from backend.services.research_service import generate_research_options, validate_options_against_metadata
from pydantic import BaseModel

router = APIRouter(prefix="/api/research", tags=["research"])

class ResearchOptionsRequest(BaseModel):
    accession: str

@router.post("/options")
def get_research_options(request: ResearchOptionsRequest):
    metadata = fetch_geo_metadata(request.accession)
    if "error" in metadata:
        raise HTTPException(status_code=404, detail=metadata["error"])

    options = generate_research_options(metadata)
    options = validate_options_against_metadata(options, metadata)

    feasible = [o for o in options if o.get("feasible") and "error" not in o]
    infeasible = [o for o in options if not o.get("feasible") and "error" not in o]

    return {
        "accession": request.accession,
        "technology": metadata.get("technology"),
        "sample_count": metadata.get("sample_count"),
        "feasible_analyses": feasible,
        "infeasible_analyses": infeasible,
        "total": len(options)
    }
