"""
Agent 1: Literature Search Agent
- Builds PICO-based search queries
- Queries PubMed API (Entrez)
- Returns structured search results
"""
import json
import anthropic
from shared.prompts import SEARCH_AGENT_PROMPT
from shared.models import PICO, SearchResult


def run_search_agent(pico: PICO, date_range: tuple = ("2000/01/01", "2025/12/31")) -> SearchResult:
    """
    Given a PICO, generate optimized search queries and retrieve literature.
    Returns a SearchResult object.
    """
    client = anthropic.Anthropic()

    user_message = f"""
    Please create a comprehensive search strategy for this meta-analysis:

    PICO:
    - Population: {pico.population}
    - Intervention: {pico.intervention}
    - Comparison: {pico.comparison}
    - Outcome: {pico.outcome}
    - Study Design filter: {pico.study_design or 'RCT preferred'}
    - Date range: {date_range[0]} to {date_range[1]}

    Generate:
    1. MeSH terms for each PICO element
    2. Free-text synonyms
    3. Full PubMed search string (with Boolean operators)
    4. Cochrane Library search string
    5. Embase search string

    Return ONLY valid JSON matching this schema:
    {{
      "mesh_terms": {{"P": [...], "I": [...], "C": [...], "O": [...]}},
      "free_text": {{"P": [...], "I": [...], "C": [...], "O": [...]}},
      "pubmed_query": "...",
      "cochrane_query": "...",
      "embase_query": "...",
      "estimated_results": integer,
      "notes": "..."
    }}
    """

    print("[Agent 1: Search] Generating search strategy...")
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        system=SEARCH_AGENT_PROMPT,
        messages=[{"role": "user", "content": user_message}]
    )

    raw = response.content[0].text
    # Strip markdown fences if present
    clean = raw.strip().replace("```json", "").replace("```", "").strip()
    data = json.loads(clean)

    # Flatten mesh terms into list
    all_mesh = []
    for terms in data.get("mesh_terms", {}).values():
        all_mesh.extend(terms)

    result = SearchResult(
        pico=pico,
        mesh_terms=all_mesh,
        pubmed_query=data["pubmed_query"],
        cochrane_query=data["cochrane_query"],
        embase_query=data["embase_query"],
        total_hits=data.get("estimated_results", 0),
        studies=[]
    )

    print(f"[Agent 1: Search] ✓ PubMed query generated")
    print(f"  → Estimated hits: {result.total_hits}")
    print(f"  → PubMed: {result.pubmed_query[:120]}...")

    return result


# ── Optional: fetch real PubMed results via Entrez ──────────────────────────
def fetch_pubmed_results(query: str, max_results: int = 200) -> list:
    """
    Fetch PMIDs from PubMed using Bio.Entrez.
    Requires: pip install biopython
    Set NCBI email as env variable: NCBI_EMAIL
    """
    try:
        from Bio import Entrez
        import os
        Entrez.email = os.getenv("NCBI_EMAIL", "researcher@example.com")

        # Search
        handle = Entrez.esearch(db="pubmed", term=query, retmax=max_results)
        record = Entrez.read(handle)
        handle.close()
        pmids = record["IdList"]

        # Fetch abstracts
        handle = Entrez.efetch(db="pubmed", id=pmids, rettype="abstract", retmode="xml")
        records = Entrez.read(handle)
        handle.close()

        studies = []
        for article in records.get("PubmedArticle", []):
            medline = article["MedlineCitation"]
            art = medline["Article"]
            studies.append({
                "pmid": str(medline["PMID"]),
                "title": str(art.get("ArticleTitle", "")),
                "abstract": str(art.get("Abstract", {}).get("AbstractText", [""])[0]),
                "year": int(art.get("Journal", {}).get("JournalIssue", {})
                           .get("PubDate", {}).get("Year", 0) or 0),
                "authors": [
                    f"{a.get('LastName', '')} {a.get('Initials', '')}"
                    for a in art.get("AuthorList", [])
                ]
            })

        print(f"[Agent 1: Search] ✓ Fetched {len(studies)} abstracts from PubMed")
        return studies

    except ImportError:
        print("[Agent 1: Search] ⚠ biopython not installed. Run: pip install biopython")
        return []
    except Exception as e:
        print(f"[Agent 1: Search] ✗ PubMed fetch error: {e}")
        return []


if __name__ == "__main__":
    # Test
    test_pico = PICO(
        population="Type 2 diabetes mellitus patients",
        intervention="SGLT2 inhibitors (empagliflozin, dapagliflozin, canagliflozin)",
        comparison="Placebo or standard care",
        outcome="Major adverse cardiovascular events (MACE)",
        study_design="Randomized controlled trial"
    )
    result = run_search_agent(test_pico)
    print("\nPubMed Query:")
    print(result.pubmed_query)
