# backend/services/pipeline_service.py

from backend.services.llm_service import call_llm
from backend.models.pipeline import PipelineStep
import json

# ── Deterministic tool registry ──────────────────────────────────────────────
TECHNOLOGY_TOOLS = {
    "methylation": {
        "import":         "minfi",
        "qc":             "minfi (plotQC, detectionP)",
        "normalization":  "minfi (preprocessFunnorm or preprocessQuantile)",
        "filtering":      "minfi (dropLociWithSnps, dropXY)",
        "differential":   "limma (lmFit + eBayes)",
        "dmr":            "bumphunter or DMRcate",
        "annotation":     "IlluminaHumanMethylation450kanno or IlluminaHumanMethylationEPICanno",
        "enrichment":     "missMethyl (gometh) — NOT GOseq, NOT clusterProfiler",
        "classification": "randomForest (R) or sklearn RandomForestClassifier (Python)",
        "clustering":     "hclust + pheatmap or umap",
        "visualization":  "ggplot2 + pheatmap",
        "forbidden":      "DESeq2, edgeR, GOseq, STAR, featureCounts, Salmon — these are RNA-seq tools, never use for methylation"
    },
    "rna-seq": {
        "qc":             "FastQC + MultiQC",
        "trimming":       "Trimmomatic or fastp",
        "alignment":      "STAR or HISAT2",
        "quantification": "featureCounts or Salmon + tximport",
        "differential":   "DESeq2 or edgeR",
        "enrichment":     "gseapy (GSEA) or clusterProfiler",
        "visualization":  "ggplot2 + EnhancedVolcano + pheatmap",
        "forbidden":      "minfi, bumphunter, ChAMP, missMethyl — these are methylation tools, never use for RNA-seq"
    },
    "scrna-seq": {
        "import":         "Scanpy (sc.read_10x_mtx)",
        "qc":             "Scanpy (sc.pp.filter_cells, sc.pp.filter_genes)",
        "normalization":  "Scanpy (sc.pp.normalize_total, sc.pp.log1p)",
        "hvg":            "Scanpy (sc.pp.highly_variable_genes)",
        "pca":            "Scanpy (sc.tl.pca)",
        "neighbors":      "Scanpy (sc.pp.neighbors)",
        "clustering":     "Scanpy (sc.tl.leiden)",
        "umap":           "Scanpy (sc.tl.umap)",
        "differential":   "Scanpy (sc.tl.rank_genes_groups)",
        "visualization":  "Scanpy (sc.pl.umap, sc.pl.dotplot)",
        "forbidden":      "DESeq2, minfi, STAR — use Scanpy equivalents for scRNA-seq"
    },
    "atac-seq": {
        "qc":             "FastQC + ATACseqQC",
        "alignment":      "Bowtie2",
        "filtering":      "samtools (remove duplicates, mitochondrial reads)",
        "peak_calling":   "MACS2",
        "differential":   "DiffBind",
        "motif":          "Homer (findMotifsGenome.pl) or JASPAR",
        "visualization":  "deeptools (bamCoverage, plotHeatmap)",
        "forbidden":      "DESeq2 for peak calling, minfi — wrong data type"
    }
}

PIPELINE_TEMPLATES = {
    "methylation": {
        "classification": [
            ("Import IDAT files",          "minfi",              "IDAT files from GEO",              "RGChannelSet object"),
            ("Quality Control",            "minfi (plotQC)",     "RGChannelSet",                     "QC report + flagged samples"),
            ("Normalization",              "minfi (preprocessFunnorm)", "Filtered RGChannelSet",     "Normalized MethylSet (beta values)"),
            ("Filter probes",              "minfi (dropLociWithSnps)", "MethylSet",                  "Clean beta matrix"),
            ("Feature selection",          "limma (lmFit)",      "Beta matrix",                      "Top variable CpG probes"),
            ("Train classifier",           "randomForest",       "Selected CpG probes + labels",     "Trained RF model"),
            ("Evaluate classifier",        "randomForest (confusion matrix)", "Trained model + test set", "Accuracy, AUC, confusion matrix"),
            ("Visualize results",          "pheatmap + ggplot2", "Classification results",            "Heatmap + ROC curve"),
        ],
        "dmr_detection": [
            ("Import IDAT files",          "minfi",              "IDAT files",                       "RGChannelSet"),
            ("Quality Control",            "minfi (plotQC)",     "RGChannelSet",                     "QC report"),
            ("Normalization",              "minfi (preprocessFunnorm)", "RGChannelSet",              "Beta values matrix"),
            ("Filter probes",              "minfi (dropLociWithSnps)", "Beta matrix",                "Clean beta matrix"),
            ("Differential methylation",   "limma (lmFit + eBayes)", "Beta matrix + design matrix", "Differentially methylated probes"),
            ("DMR detection",              "bumphunter or DMRcate", "Methylation M-values",          "DMR table with coordinates"),
            ("Annotation",                 "IlluminaHumanMethylation450kanno", "DMR table",          "Annotated DMRs with gene names"),
            ("Enrichment analysis",        "missMethyl (gometh)", "Annotated DMR gene list",         "GO + KEGG enrichment results"),
            ("Visualization",              "ggplot2 + pheatmap", "DMRs + enrichment",                "Heatmap + enrichment plots"),
        ],
        "methylation_analysis": [
            ("Import IDAT files",          "minfi",              "IDAT files",                       "RGChannelSet"),
            ("Quality Control",            "minfi (plotQC, detectionP)", "RGChannelSet",             "QC metrics + sample flags"),
            ("Normalization",              "minfi (preprocessFunnorm)", "RGChannelSet",              "Normalized beta values"),
            ("Filter low-quality probes",  "minfi",              "Beta matrix",                      "Filtered beta matrix"),
            ("Global methylation summary", "minfi",              "Beta matrix",                      "Per-sample methylation distribution"),
            ("Clustering",                 "hclust + pheatmap",  "Beta matrix (top variable CpGs)",  "Sample dendrogram + heatmap"),
            ("Dimensionality reduction",   "umap (Python) or Rtsne (R)", "Beta matrix",             "UMAP/tSNE plot"),
            ("Visualization",              "ggplot2",            "All results",                      "Publication-ready figures"),
        ],
        "clustering": [
            ("Import IDAT files",          "minfi",              "IDAT files",                       "RGChannelSet"),
            ("Quality Control",            "minfi",              "RGChannelSet",                     "QC report"),
            ("Normalization",              "minfi (preprocessFunnorm)", "RGChannelSet",              "Beta matrix"),
            ("Select variable CpGs",       "matrixStats (rowVars)", "Beta matrix",                   "Top 10k variable CpG sites"),
            ("Dimensionality reduction",   "umap",               "Variable CpG matrix",              "2D embedding"),
            ("Clustering",                 "hclust or k-means",  "Variable CpG matrix",              "Cluster assignments"),
            ("Cluster characterization",   "limma",              "Clusters + beta matrix",           "Cluster-specific DMPs"),
            ("Visualization",              "pheatmap + ggplot2", "Clusters + UMAP",                  "Cluster heatmap + UMAP colored by cluster"),
        ]
    },
    "rna-seq": {
        "diff_exp": [
            ("Quality Control",            "FastQC + MultiQC",   "Raw FASTQ files",                  "QC report"),
            ("Trimming",                   "fastp",              "Raw FASTQ",                         "Trimmed FASTQ"),
            ("Alignment",                  "STAR",               "Trimmed FASTQ + genome reference",  "BAM files"),
            ("Quantification",             "featureCounts",      "BAM files + GTF annotation",        "Count matrix"),
            ("Differential expression",    "DESeq2",             "Count matrix + sample metadata",    "DEG table"),
            ("Visualization",              "EnhancedVolcano + pheatmap", "DEG results",              "Volcano plot + heatmap"),
            ("Enrichment analysis",        "gseapy",             "DEG list",                          "GO + KEGG enrichment"),
        ]
    }
}

def detect_technology_class(technology: str) -> str:
    tech = technology.lower()
    if "methylation" in tech or "bisulfite" in tech:
        return "methylation"
    if "scrna" in tech or "single cell" in tech or "10x" in tech:
        return "scrna-seq"
    if "rna-seq" in tech or "rna seq" in tech or "expression" in tech or "transcriptom" in tech:
        return "rna-seq"
    if "atac" in tech:
        return "atac-seq"
    return "unknown"


def get_template_steps(tech_class: str, analysis_id: str) -> list:
    """Return hardcoded steps if a template exists for this combo."""
    tech_templates = PIPELINE_TEMPLATES.get(tech_class, {})

    # try exact match first
    if analysis_id in tech_templates:
        return tech_templates[analysis_id]

    # fuzzy match
    for key in tech_templates:
        if key in analysis_id or analysis_id in key:
            return tech_templates[key]

    return []


def build_steps_from_template(template: list) -> list:
    """Convert template tuples into PipelineStep dicts."""
    steps = []
    for i, (name, tool, inp, out) in enumerate(template, 1):
        steps.append({
            "step_id": i,
            "name": name,
            "tool": tool,
            "why": "",        # LLM will fill this in
            "input": inp,
            "output": out,
            "decision_point": False,
            "decision_logic": None,
            "estimated_time": None
        })
    return steps


def enrich_steps_with_llm(steps: list, metadata: dict, selected_option: dict, tech_class: str) -> list:
    """
    LLM only fills in 'why' and 'estimated_time' for each step.
    Tool names and data flow are already locked in from the template.
    """
    tools = TECHNOLOGY_TOOLS.get(tech_class, {})

    steps_text = "\n".join([
        f"Step {s['step_id']}: {s['name']} using {s['tool']} | input: {s['input']} | output: {s['output']}"
        for s in steps
    ])

    system_prompt = f"""You are a bioinformatics expert.
For each pipeline step below, provide:
1. A scientific reason WHY this step is necessary (1-2 sentences)
2. A realistic time estimate

Return ONLY a JSON array. No explanation. No markdown. No backticks.

Data type: {tech_class}
Organism: {metadata.get('organism')}
Analysis: {selected_option.get('title')}

Return this structure:
[
  {{
    "step_id": 1,
    "why": "scientific reason this step is necessary",
    "estimated_time": "X minutes",
    "decision_point": false,
    "decision_logic": null
  }}
]

For QC steps: add decision_point: true with logic for pass/fail criteria.
For normalization steps: explain which method is appropriate and why."""

    user_message = f"""Pipeline steps to annotate:
{steps_text}

Return the JSON array with why and estimated_time for each step."""

    raw = call_llm([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ], temperature=0.2)

    if "```" in raw:
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    if not raw.endswith("]"):
        last = raw.rfind("},")
        raw = (raw[:last + 1] if last != -1 else raw) + "]"

    try:
        annotations = json.loads(raw)
        ann_map = {a["step_id"]: a for a in annotations}
        for step in steps:
            ann = ann_map.get(step["step_id"], {})
            step["why"] = ann.get("why", f"Standard {step['name'].lower()} step for {tech_class} data")
            step["estimated_time"] = ann.get("estimated_time", "varies")
            step["decision_point"] = ann.get("decision_point", False)
            step["decision_logic"] = ann.get("decision_logic", None)
        return steps
    except Exception:
        # fallback: return steps with generic why
        for step in steps:
            step["why"] = f"Standard {step['name'].lower()} step for {tech_class} analysis"
            step["estimated_time"] = "varies"
        return steps


def generate_pipeline_hypothesis(metadata: dict, selected_option: dict) -> dict:
    """LLM generates research question and hypothesis only."""

    prompt = f"""You are a bioinformatics scientist.
Given this dataset and analysis, return ONLY a JSON object with two fields.
No markdown. No backticks. Pure JSON.

{{
  "research_question": "formal one-sentence biological research question",
  "hypothesis": "testable hypothesis for this specific analysis"
}}

Dataset: {metadata.get('accession')} — {metadata.get('title')}
Organism: {metadata.get('organism')}
Technology: {metadata.get('technology')}
Analysis: {selected_option.get('title')} — {selected_option.get('question')}"""

    raw = call_llm([{"role": "user", "content": prompt}], temperature=0.2)

    if "```" in raw:
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        return json.loads(raw)
    except Exception:
        return {
            "research_question": selected_option.get("question", ""),
            "hypothesis": f"We hypothesize that {selected_option.get('question', '').lower()}"
        }


def generate_pipeline(metadata: dict, selected_option: dict) -> dict:
    """
    Hybrid pipeline generator:
    - Tool selection: deterministic (from template)
    - Scientific rationale: LLM
    - Hypothesis: LLM
    """
    tech_class = detect_technology_class(metadata.get("technology", ""))
    analysis_id = selected_option.get("id", "")
    tools = TECHNOLOGY_TOOLS.get(tech_class, {})

    # get hardcoded template steps
    template = get_template_steps(tech_class, analysis_id)

    if template:
        steps = build_steps_from_template(template)
        # LLM only fills in why + time estimates
        steps = enrich_steps_with_llm(steps, metadata, selected_option, tech_class)
    else:
        # no template — fall back to full LLM but constrain tools
        forbidden = tools.get("forbidden", "")
        allowed_tools = {k: v for k, v in tools.items() if k != "forbidden"}

        system_prompt = f"""You are a senior bioinformatics scientist.
Generate a pipeline for {tech_class} data analysis.
Return ONLY a JSON array of steps. No markdown. No backticks.

ALLOWED TOOLS for {tech_class}:
{json.dumps(allowed_tools, indent=2)}

FORBIDDEN (never use these): {forbidden}

Each step:
{{
  "step_id": 1,
  "name": "step name",
  "tool": "tool from allowed list only",
  "why": "scientific reason",
  "input": "input data",
  "output": "output produced",
  "decision_point": false,
  "decision_logic": null,
  "estimated_time": "X minutes"
}}"""

        user_message = f"""Dataset: {metadata.get('accession')}
Technology: {metadata.get('technology')}
Organism: {metadata.get('organism')}
Analysis: {selected_option.get('title')} — {selected_option.get('question')}

Generate 6-8 pipeline steps using only the allowed tools."""

        raw = call_llm([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ], temperature=0.1)

        if "```" in raw:
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        if not raw.endswith("]"):
            last = raw.rfind("},")
            raw = (raw[:last + 1] if last != -1 else raw) + "]"

        try:
            steps = json.loads(raw)
        except Exception as e:
            return {"error": f"Pipeline generation failed: {str(e)}", "raw": raw}

    # generate hypothesis separately
    framing = generate_pipeline_hypothesis(metadata, selected_option)

    return {
        "research_question": framing.get("research_question", ""),
        "hypothesis":        framing.get("hypothesis", ""),
        "analysis_type":     selected_option.get("title", ""),
        "dataset_accession": metadata.get("accession"),
        "technology_class":  tech_class,
        "steps":             steps,
        "expected_outputs":  selected_option.get("expected_outputs", []),
        "provenance": {
            "dataset":              metadata.get("accession"),
            "organism":             metadata.get("organism"),
            "technology":           metadata.get("technology"),
            "statistical_threshold":"FDR < 0.05",
            "tools_required":       list({s["tool"].split(" ")[0] for s in steps})
        }
    }
