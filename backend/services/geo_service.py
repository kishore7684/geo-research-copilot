# backend/services/geo_service.py

from Bio import Entrez
from dotenv import load_dotenv
import os
import re
import time

load_dotenv(dotenv_path="backend/.env")
Entrez.email = os.getenv("NCBI_EMAIL")


def detect_source(url_or_id: str) -> dict:
    url = url_or_id.strip()

    if re.search(r'GSE\d+', url, re.IGNORECASE):
        match = re.search(r'GSE\d+', url, re.IGNORECASE)
        return {"source": "GEO", "accession": match.group().upper()}

    if re.search(r'pubmed\.ncbi', url) or re.search(r'PMID:?\s*\d+', url):
        match = re.search(r'\d+', url.split('pubmed')[-1])
        if match:
            return {"source": "PubMed", "accession": match.group()}

    if re.search(r'SRP\d+|SRR\d+', url, re.IGNORECASE):
        match = re.search(r'SR[PR]\d+', url, re.IGNORECASE)
        return {"source": "SRA", "accession": match.group().upper()}

    return {"source": "unknown", "accession": url}


def extract_sample_conditions(samples: list, max_samples: int = 50) -> list:
    """Extract unique condition labels from sample titles."""
    if not samples:
        return []

    titles = []
    for s in samples[:max_samples]:
        if isinstance(s, dict):
            title = str(s.get("Title", "") or s.get("title", ""))
            if title:
                titles.append(title)

    # deduplicate while preserving order
    seen = set()
    unique = []
    for t in titles:
        if t not in seen:
            seen.add(t)
            unique.append(t)

    return unique[:30]


def fetch_geo_metadata(accession: str) -> dict:
    """Fetch real GEO metadata using Biopython esummary."""
    try:
        # use [accn] for precise match
        handle = Entrez.esearch(db="gds", term=f"{accession}[accn]")
        record = Entrez.read(handle)
        handle.close()

        if not record["IdList"]:
            # fallback to general search
            handle = Entrez.esearch(db="gds", term=accession)
            record = Entrez.read(handle)
            handle.close()

        if not record["IdList"]:
            return {"error": f"No GEO record found for {accession}"}

        geo_id = record["IdList"][0]

        time.sleep(0.34)  # NCBI rate limit

        handle = Entrez.esummary(db="gds", id=geo_id, report="full")
        summary = Entrez.read(handle)
        handle.close()

        if not summary:
            return {"error": "Empty summary returned"}

        rec = summary[0]

        # extract sample conditions from sample list
        samples_raw = list(rec.get("Samples", []))
        sample_conditions = extract_sample_conditions(samples_raw)

        # supplementary files tell us what data is available
        supp_files = str(rec.get("suppFile", ""))

        metadata = {
            "accession": accession,
            "title": str(rec.get("title", "")),
            "summary": str(rec.get("summary", ""))[:3000],
            "organism": str(rec.get("taxon", "")),
            "technology": str(rec.get("gdsType", "")),
            "sample_count": int(rec.get("n_samples", 0)),
            "platform": str(rec.get("GPL", "")),
            "pubmed_ids": list(rec.get("PubMedIds", [])),
            "ftp_link": str(rec.get("FTPLink", "")),
            "supplementary_files": supp_files,
            "sample_conditions": sample_conditions,
            "entry_type": str(rec.get("entryType", "")),
            "submission_date": str(rec.get("PDAT", "")),
        }

        return metadata

    except Exception as e:
        return {"error": str(e)}

