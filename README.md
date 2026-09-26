# 🧬 GEO Research Copilot

An AI-powered bioinformatics research assistant. Paste a GEO accession number — the system fetches real dataset metadata, understands the biology, proposes feasible research directions, and generates a full step-by-step computational pipeline with scientific rationale for every step.

**Live Demo:** https://huggingface.co/spaces/Kishore7684/geo-research-copilot  
**Backend API:** https://your-render-url.onrender.com/docs

---

## What It Does

**Stage 1 — Dataset Intelligence**  
Fetches real metadata from NCBI GEO using Biopython. Sends structured data (not raw URLs) to an LLM which returns a validated JSON summary of the study — research question, biological context, experimental design, key comparison.

**Stage 2 — Research Discovery**  
Generates 5-7 research directions actually supported by the dataset. Uses a hybrid approach: LLM proposes options, deterministic Python validates feasibility against real metadata (technology type, sample count, available files).

**Stage 3 — Pipeline Planner**  
User selects an analysis → system generates a full computational pipeline with correct tools per data type, scientific rationale for every step, decision points with pass/fail logic, and provenance tracking.

---

## Key Architectural Decisions

- **LLM never sees raw URLs.** Biopython fetches verified structured metadata first. LLM only receives clean JSON.
- **Tool selection is deterministic, not LLM-generated.** A hardcoded registry maps data types to correct tools. LLM only fills in scientific rationale. DESeq2 will never appear in a methylation pipeline.
- **Rule-based feasibility validation.** Python checks sample count, technology type, and available files before marking any analysis feasible.

---

## Architecture

User pastes GEO accession
↓
Source Detector (regex-based)
↓
GEO Service (Biopython + NCBI API) → verified structured metadata
↓
LLM (few-shot prompted) → dataset summary JSON
↓
Research Options Generator (LLM + rule-based validation)
↓
User selects analysis
↓
Pipeline Planner (hardcoded tool registry + LLM rationale)
↓
Step-by-step pipeline with scientific reasoning


---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + Python |
| GEO Fetch | Biopython (NCBI Entrez API) |
| LLM | OpenRouter API (Llama 3.1 8B) |
| Validation | Pydantic |
| Database | SQLite + SQLModel |
| Frontend | Streamlit |
| Backend Deploy | Render |
| Frontend Deploy | Hugging Face Spaces |

---

## Supported Data Types

| Technology | Tools Used |
|---|---|
| Methylation array | minfi, limma, bumphunter, missMethyl, randomForest |
| RNA-seq | STAR, featureCounts, DESeq2, gseapy |
| scRNA-seq | Scanpy |
| ATAC-seq | Bowtie2, MACS2, DiffBind, Homer |

---

## Example Datasets to Try

| Accession | Description | Type |
|---|---|---|
| GSE90496 | CNS tumor methylation classifier (2801 samples) | Methylation array |
| GSE99884 | Clioquinol treatment in yeast | RNA-seq |

---

## Local Setup

```bash
git clone https://github.com/kishore7684/geo-research-copilot
cd geo-research-copilot

python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# create backend/.env
OPENROUTER_API_KEY=your_key
NCBI_EMAIL=your_email
DATABASE_URL=sqlite:///./geo_copilot.db

# terminal 1
uvicorn backend.main:app --reload

# terminal 2
streamlit run frontend/app.py
```

---

## Roadmap

- [ ] Phase 4a: Python execution layer (pandas, Scanpy QC steps)
- [ ] Phase 4b: R execution via subprocess (DESeq2, minfi)
- [ ] Phase 4c: Async job execution (Celery + Redis)
- [ ] Phase 4d: Results interpretation agent
- [ ] Phase 5: React frontend
- [ ] PubMed URL support
- [ ] Docker containerization

---

## Author

Kishore — B.Tech Biotechnology, NIT Durgapur  
Bioinformatics Intern @ Strand Life Sciences  
[GitHub](https://github.com/kishore7684)
