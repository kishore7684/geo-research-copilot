# backend/services/pipeline_service.py

from backend.services.llm_service import call_llm
from backend.models.pipeline import PipelineStep, PipelinePlan
import json

def generate_pipeline(metadata: dict, selected_option: dict) -> dict:
    """
    Given dataset metadata and selected research option,
    generate a full step-by-step computational pipeline.
    """

    system_prompt = """You are a senior bioinformatics scientist.
Given a GEO dataset and a selected analysis type, generate a detailed computational pipeline.
Return ONLY a JSON object. No explanation. No markdown. No backticks.

Return exactly this structure:
{
  "research_question": "formal statement of the biological question",
  "hypothesis": "testable hypothesis for this analysis",
  "analysis_type": "name of the analysis",
  "steps": [
    {
      "step_id": 1,
      "name": "step name",
      "tool": "specific tool or library to use",
      "why": "scientific reason this step is necessary",
      "input": "what this step takes as input",
      "output": "what this step produces",
      "decision_point": false,
      "decision_logic": null,
      "estimated_time": "time estimate e.g. 5 minutes"
    }
  ],
  "expected_outputs": ["final output 1", "final output 2"],
  "provenance": {
    "dataset": "accession number",
    "organism": "organism name",
    "technology": "data type",
    "statistical_threshold": "e.g. FDR < 0.05",
    "tools_required": ["tool1", "tool2"]
  }
}

Rules:
- Generate 6 to 10 steps in logical order
- Every step must have a clear scientific reason in the why field
- Use real bioinformatics tools (DESeq2, minfi, Scanpy, limma, etc.)
- Add decision_point: true for steps where the pipeline branches based on results
- For decision points add decision_logic explaining what to do in each case
- Steps must flow logically — output of step N is input of step N+1
- Be specific about tools based on the data type:
  - RNA-seq: DESeq2, edgeR, Salmon, STAR, featureCounts
  - Methylation array: minfi, ChAMP, bumphunter, limma
  - scRNA-seq: Scanpy, Seurat, scanpy
  - ATAC-seq: MACS2, deeptools, Homer"""

    user_message = f"""Dataset:
Accession: {metadata.get('accession')}
Organism: {metadata.get('organism')}
Technology: {metadata.get('technology')}
Sample count: {metadata.get('sample_count')}
Summary: {metadata.get('summary', '')[:1000]}
Supplementary files: {metadata.get('supplementary_files', '')}
Sample conditions: {', '.join(metadata.get('sample_conditions', [])[:10])}

Selected analysis:
Title: {selected_option.get('title')}
Question: {selected_option.get('question')}
Required data: {', '.join(selected_option.get('required_data', []))}
Expected outputs: {', '.join(selected_option.get('expected_outputs', []))}

Generate the computational pipeline."""

    raw = call_llm([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ], temperature=0.2)

    # strip markdown fences
    if "```" in raw:
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    # fix truncation
    if not raw.endswith("}"):
        open_braces = raw.count("{") - raw.count("}")
        open_brackets = raw.count("[") - raw.count("]")
        if raw and raw[-1] not in ('"', '}', ']'):
            raw += '"'
        raw += "]" * open_brackets
        raw += "}" * open_braces

    try:
        parsed = json.loads(raw)

        # validate steps
        validated_steps = []
        for step in parsed.get("steps", []):
            try:
                s = PipelineStep(**step)
                validated_steps.append(s.model_dump())
            except Exception:
                continue

        parsed["steps"] = validated_steps
        parsed["dataset_accession"] = metadata.get("accession")

        return parsed

    except Exception as e:
        return {"error": f"Pipeline generation failed: {str(e)}", "raw": raw}
