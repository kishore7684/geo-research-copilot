# backend/services/llm_service.py

import requests
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Optional
import os
import json

load_dotenv(dotenv_path="backend/.env")

API_URL = "https://openrouter.ai/api/v1/chat/completions"

class StudySummary(BaseModel):
    research_question: str
    biological_context: str
    experimental_design: str
    data_type: str
    organism: str
    key_comparison: Optional[str] = None
    potential_value: str

def call_llm(messages: list, temperature: float = 0.2) -> str:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise Exception("OPENROUTER_API_KEY not found in environment")

    response = requests.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "meta-llama/llama-3.1-8b-instruct",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 2000,
        }
    )

    if response.status_code != 200:
        raise Exception(f"OpenRouter error {response.status_code}: {response.text}")

    return response.json()["choices"][0]["message"]["content"].strip()


def fix_truncated_json(raw: str) -> str:
    raw = raw.strip()
    open_braces = raw.count("{") - raw.count("}")
    open_brackets = raw.count("[") - raw.count("]")
    if raw and raw[-1] not in ('"', '}', ']', ','):
        raw += '"'
    raw += "]" * open_brackets
    raw += "}" * open_braces
    return raw


def summarize_dataset(metadata: dict) -> dict:

    system_prompt = """You are a bioinformatics expert. Analyze GEO dataset metadata and return a JSON object.
Return ONLY valid JSON. No explanation. No markdown. No backticks.

EXAMPLE INPUT:
Title: RNA-seq profiling of BRCA1-mutant breast tumors vs normal tissue
Summary: We performed RNA-seq on 20 BRCA1-mutant breast tumors and 20 matched normal tissue samples to identify transcriptional changes driven by BRCA1 loss.
Technology: RNA-seq
Organism: Homo sapiens
Samples: 40

EXAMPLE OUTPUT:
{
  "research_question": "What transcriptional changes are driven by BRCA1 loss in breast tumors?",
  "biological_context": "BRCA1-mutant breast cancer",
  "experimental_design": "20 BRCA1-mutant breast tumors vs 20 matched normal tissue samples, RNA-seq",
  "data_type": "RNA-seq",
  "organism": "Homo sapiens",
  "key_comparison": "BRCA1-mutant tumor vs normal tissue",
  "potential_value": "Identifies transcriptional programs disrupted by BRCA1 loss, potential therapeutic targets"
}

Now analyze the dataset below and return a JSON object in the same format."""

    user_message = f"""Title: {metadata.get('title')}
Summary: {metadata.get('summary')}
Technology: {metadata.get('technology')}
Organism: {metadata.get('organism')}
Samples: {metadata.get('sample_count')}
Sample conditions: {', '.join(metadata.get('sample_conditions', [])[:10])}"""

    raw = call_llm([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ])

    if "```" in raw:
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        parsed = json.loads(raw)
        validated = StudySummary(**parsed)
        return validated.model_dump()
    except json.JSONDecodeError:
        pass

    try:
        fixed = fix_truncated_json(raw)
        parsed = json.loads(fixed)
        validated = StudySummary(**parsed)
        return validated.model_dump()
    except Exception as e:
        return {"error": f"LLM returned invalid JSON: {str(e)}", "raw": raw}
