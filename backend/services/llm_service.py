import requests
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Optional
import os
import json
import re

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
    """Fix JSON truncated by token limit — close open strings and braces."""
    raw = raw.strip()

    # count open vs closed braces
    open_braces = raw.count("{") - raw.count("}")
    open_brackets = raw.count("[") - raw.count("]")

    # if last char is not a quote or brace, we're mid-string — close it
    if raw and raw[-1] not in ('"', '}', ']', ','):
        raw += '"'

    # close any open brackets
    raw += "]" * open_brackets

    # close any open braces
    raw += "}" * open_braces

    return raw


def summarize_dataset(metadata: dict) -> dict:

    system_prompt = """You are a bioinformatics expert analyzing GEO datasets.
Analyze the metadata and return ONLY valid JSON. No explanation. No markdown. No backticks.

Return exactly this JSON structure with real values:
{
  "research_question": "the actual biological question this study investigates",
  "biological_context": "the disease or biological process being studied",
  "experimental_design": "actual groups conditions and sample sizes",
  "data_type": "actual technology used",
  "organism": "actual organism name",
  "key_comparison": "actual comparison being made",
  "potential_value": "why this dataset matters scientifically"
}"""

    user_message = f"""Analyze this GEO dataset:

Accession: {metadata.get('accession')}
Title: {metadata.get('title')}
Summary: {metadata.get('summary')}
Organism: {metadata.get('organism')}
Technology: {metadata.get('technology')}
Sample count: {metadata.get('sample_count')}
Platform: {metadata.get('platform')}

Return only the JSON object."""

    raw = call_llm([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ])

    # strip markdown fences
    if "```" in raw:
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    # attempt 1: parse as-is
    try:
        parsed = json.loads(raw)
        validated = StudySummary(**parsed)
        return validated.model_dump()
    except json.JSONDecodeError:
        pass

    # attempt 2: fix truncation and retry
    try:
        fixed = fix_truncated_json(raw)
        parsed = json.loads(fixed)
        validated = StudySummary(**parsed)
        return validated.model_dump()
    except Exception as e:
        return {"error": f"LLM returned invalid JSON: {str(e)}", "raw": raw}
