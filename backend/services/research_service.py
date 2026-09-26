# backend/services/research_service.py

from backend.services.llm_service import call_llm
from backend.models.research import ResearchOption
import json

def generate_research_options(metadata: dict) -> list:
    """Given dataset metadata, return feasible research directions."""

    system_prompt = """You are a bioinformatics expert.
Given GEO dataset metadata, propose research analyses that are actually supported by this data.
Return ONLY a JSON array. No explanation. No markdown. No backticks.

Each item must follow this exact structure:
{
  "id": "short_snake_case_id",
  "title": "Analysis Title",
  "question": "The biological question this answers",
  "required_data": ["data type 1", "data type 2"],
  "expected_outputs": ["output 1", "output 2", "output 3"],
  "feasible": true or false,
  "feasibility_reason": "why this is or is not possible with this dataset",
  "difficulty": "beginner or intermediate or advanced"
}

Rules:
- Only propose analyses the dataset can actually support based on its technology and metadata
- If RNA-seq: differential expression, pathway analysis, clustering, GSEA are feasible
- If methylation array: methylation analysis, DMR detection, classification are feasible  
- If ATAC-seq: chromatin accessibility, peak analysis, motif analysis are feasible
- Mark infeasible analyses with feasible: false and explain why
- Propose 5 to 7 options total, mix of feasible and infeasible"""

    user_message = f"""Dataset metadata:
Accession: {metadata.get('accession')}
Title: {metadata.get('title')}
Summary: {metadata.get('summary')}
Organism: {metadata.get('organism')}
Technology: {metadata.get('technology')}
Sample count: {metadata.get('sample_count')}

Return the JSON array of research options."""

    raw = call_llm([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ], temperature=0.3)

    # strip markdown fences
    if "```" in raw:
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    # fix truncation
    if not raw.endswith("]"):
        # remove last incomplete object
        last_complete = raw.rfind("},")
        if last_complete != -1:
            raw = raw[:last_complete + 1] + "]"
        else:
            raw = raw + "]"

    try:
        parsed = json.loads(raw)
        # validate each option
        validated = []
        for item in parsed:
            try:
                option = ResearchOption(**item)
                validated.append(option.model_dump())
            except Exception:
                continue
        return validated
    except Exception as e:
        return [{"error": f"Failed to parse research options: {str(e)}", "raw": raw}]


def validate_options_against_metadata(options: list, metadata: dict) -> list:
    """
    Rule-based validation layer.
    Don't trust LLM alone to check feasibility — verify with Python.
    """
    technology = metadata.get("technology", "").lower()
    sample_count = metadata.get("sample_count", 0)

    for option in options:
        if "error" in option:
            continue

        oid = option.get("id", "")

        # override LLM feasibility with hard rules
        if "diff_exp" in oid or "differential" in oid.lower():
            if sample_count < 4:
                option["feasible"] = False
                option["feasibility_reason"] = f"Only {sample_count} samples — need at least 4 for differential expression"

        if "methylation" in oid.lower() or "dmr" in oid.lower():
            if "methylation" not in technology and "bisulfite" not in technology:
                option["feasible"] = False
                option["feasibility_reason"] = "Dataset is not methylation-based"

        if "atac" in oid.lower() or "chromatin" in oid.lower():
            if "atac" not in technology:
                option["feasible"] = False
                option["feasibility_reason"] = "Dataset does not contain ATAC-seq data"

        if "rna" in oid.lower() or "expression" in oid.lower():
            if "rna" not in technology and "expression" not in technology and "seq" not in technology:
                option["feasible"] = False
                option["feasibility_reason"] = "Dataset does not contain RNA-seq data"

    return options
