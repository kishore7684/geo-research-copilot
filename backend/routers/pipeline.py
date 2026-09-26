# backend/routers/pipeline.py

from fastapi import APIRouter, HTTPException
from backend.services.geo_service import fetch_geo_metadata
from backend.services.pipeline_service import generate_pipeline
from backend.services.research_service import generate_research_options, validate_options_against_metadata
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

class PipelineRequest(BaseModel):
    accession: str
    analysis_id: str
    custom_objective: Optional[str] = None

@router.post("/plan")
def plan_pipeline(request: PipelineRequest):

    # fetch metadata
    metadata = fetch_geo_metadata(request.accession)
    if "error" in metadata:
        raise HTTPException(status_code=404, detail=metadata["error"])

    # get research options to find the selected one
    options = generate_research_options(metadata)
    options = validate_options_against_metadata(options, metadata)

    # find selected option by id
    selected = None
    for opt in options:
        if opt.get("id") == request.analysis_id:
            selected = opt
            break

    # handle custom objective
    if not selected and request.custom_objective:
        selected = {
            "id": "custom",
            "title": "Custom Analysis",
            "question": request.custom_objective,
            "required_data": [],
            "expected_outputs": []
        }

    if not selected:
        raise HTTPException(
            status_code=404,
            detail=f"Analysis '{request.analysis_id}' not found for this dataset"
        )

    if not selected.get("feasible", True) and request.analysis_id != "custom":
        raise HTTPException(
            status_code=400,
            detail=f"Analysis not feasible: {selected.get('feasibility_reason')}"
        )

    # generate pipeline
    pipeline = generate_pipeline(metadata, selected)

    if "error" in pipeline:
        raise HTTPException(status_code=500, detail=pipeline["error"])

    return {
        "accession": request.accession,
        "selected_analysis": selected,
        "pipeline": pipeline
    }
