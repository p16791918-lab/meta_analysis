"""
Meta-Analysis Orchestrator
===========================
Coordinates all 5 sub-agents in sequence:
  Agent 1 → Search
  Agent 2 → Screening
  Agent 3 → Data Extraction
  Agent 4 → Statistical Analysis
  Agent 5 → Manuscript Writing

Usage:
  python orchestrator.py

Or import and call run_meta_analysis() with your PICO.
"""
import json
import os
from datetime import datetime
from shared.models import PICO, MetaAnalysisProject
from agent_1_search import run_search_agent, fetch_pubmed_results
from agent_2_screening import screen_studies, generate_prisma_text
from agent_3_extraction import extract_data, to_r_dataframe
from agent_4_analysis import run_analysis_agent, save_r_script
from agent_5_writer import write_full_manuscript, compile_manuscript


def run_meta_analysis(
    title: str,
    pico: PICO,
    inclusion_criteria: list,
    exclusion_criteria: list,
    rob_tool: str = "RoB2",
    target_journal: str = "PLOS ONE",
    protocol_doi: str = None,
    date_range: tuple = ("2000/01/01", "2025/12/31"),
    max_search_results: int = 200,
    demo_mode: bool = False           # True = use mock data instead of real PubMed
) -> MetaAnalysisProject:
    """
    Full pipeline: PICO → manuscript.
    
    Args:
        demo_mode: If True, uses synthetic studies (no PubMed API key needed)
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"output_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)

    print("\n" + "="*60)
    print("  META-ANALYSIS AGENT SYSTEM")
    print("="*60)
    print(f"  Title   : {title}")
    print(f"  Journal : {target_journal}")
    print(f"  Mode    : {'DEMO (mock data)' if demo_mode else 'LIVE (PubMed)'}")
    print("="*60 + "\n")

    project = MetaAnalysisProject(
        title=title,
        pico=pico,
        protocol_doi=protocol_doi,
        target_journal=target_journal
    )

    # ── AGENT 1: SEARCH ──────────────────────────────────────────
    print("\n[STEP 1/5] Literature Search")
    search_result = run_search_agent(pico, date_range)
    project.search_results = search_result

    # Save search queries
    with open(f"{output_dir}/search_queries.json", "w") as f:
        json.dump({
            "pubmed": search_result.pubmed_query,
            "cochrane": search_result.cochrane_query,
            "embase": search_result.embase_query,
            "mesh_terms": search_result.mesh_terms
        }, f, indent=2)

    # Fetch real or mock studies
    if demo_mode:
        studies_raw = _generate_demo_studies(pico, n=15)
        print(f"[STEP 1/5] Using {len(studies_raw)} demo studies")
    else:
        studies_raw = fetch_pubmed_results(search_result.pubmed_query, max_search_results)

    search_result.studies = studies_raw

    # ── AGENT 2: SCREENING ───────────────────────────────────────
    print("\n[STEP 2/5] Study Screening (PRISMA)")
    screening = screen_studies(
        studies_raw,
        pico,
        inclusion_criteria,
        exclusion_criteria,
        rob_tool
    )

    project.included_studies = [
        d for d in screening["decisions"]
        if d.phase2_decision == "include"
    ]
    project.prisma_numbers = screening["prisma"]
    project.rob_summary = screening["rob_summary"]

    prisma_text = generate_prisma_text(screening["prisma"])
    with open(f"{output_dir}/prisma_flow.txt", "w") as f:
        f.write(prisma_text)
    print(prisma_text)

    # ── AGENT 3: DATA EXTRACTION ─────────────────────────────────
    print("\n[STEP 3/5] Data Extraction")
    included_raw = [
        s for s in studies_raw
        if any(d.pmid == s.get("pmid") and d.phase2_decision == "include"
               for d in screening["decisions"])
    ]

    # Determine outcome type from PICO
    outcome_type = _infer_outcome_type(pico.outcome)
    extracted = extract_data(
        included_raw,
        primary_outcome_name=pico.outcome,
        outcome_type=outcome_type
    )
    project.extracted_data = extracted

    # Save R dataframe code
    r_df_code = to_r_dataframe(extracted)
    with open(f"{output_dir}/data.R", "w") as f:
        f.write(r_df_code)

    # ── AGENT 4: STATISTICAL ANALYSIS ────────────────────────────
    print("\n[STEP 4/5] Statistical Analysis")
    analysis = run_analysis_agent(
        extracted,
        subgroup_vars=["design", "follow_up_wk"],
        sensitivity_scenarios=["leave-one-out", "high-ROB excluded", "RCT only"]
    )

    project.manuscript_sections["results_narrative"] = analysis.get("results_narrative", "")
    project.manuscript_sections["grade_table"] = str(analysis.get("grade_table", {}))
    project.manuscript_sections["analysis_plan"] = analysis.get("analysis_plan", "")

    # Save R analysis script
    save_r_script(analysis.get("r_code", ""), f"{output_dir}/meta_analysis.R")

    # ── AGENT 5: MANUSCRIPT WRITING ──────────────────────────────
    print("\n[STEP 5/5] Manuscript Writing")
    sections = write_full_manuscript(project)
    project.manuscript_sections.update(sections)

    manuscript_path = f"{output_dir}/manuscript.md"
    full_text = compile_manuscript(sections, title, manuscript_path)

    # ── FINAL SUMMARY ────────────────────────────────────────────
    print("\n" + "="*60)
    print("  PIPELINE COMPLETE")
    print("="*60)
    print(f"  Output directory : {output_dir}/")
    print(f"  ├── search_queries.json")
    print(f"  ├── prisma_flow.txt")
    print(f"  ├── data.R                  (study data)")
    print(f"  ├── meta_analysis.R         (full R analysis)")
    print(f"  └── manuscript.md           (draft manuscript)")
    print(f"\n  Studies included : {len(project.included_studies)}")
    total_words = sum(len(v.split()) for v in sections.values())
    print(f"  Manuscript words : ~{total_words}")
    print("="*60 + "\n")

    return project


# ── Helper functions ────────────────────────────────────────────────────────

def _infer_outcome_type(outcome_str: str) -> str:
    binary_keywords = ["event", "mortality", "death", "incidence", "rate",
                       "mace", "stroke", "mi ", "hospitalization", "odds"]
    tte_keywords = ["survival", "time to", "hazard"]
    outcome_lower = outcome_str.lower()
    if any(k in outcome_lower for k in tte_keywords):
        return "time-to-event"
    if any(k in outcome_lower for k in binary_keywords):
        return "binary"
    return "continuous"


def _generate_demo_studies(pico: PICO, n: int = 15) -> list:
    """Generate synthetic study data for demo/testing purposes."""
    import random
    random.seed(42)
    studies = []
    first_authors = ["Kim", "Park", "Lee", "Choi", "Jung", "Han",
                     "Smith", "Johnson", "Wang", "Chen", "Müller",
                     "Tanaka", "Patel", "Santos", "Rossi"]
    years = range(2010, 2025)

    for i in range(n):
        year = random.choice(years)
        studies.append({
            "pmid": str(10000000 + i),
            "title": f"Effect of {pico.intervention} on {pico.outcome} "
                     f"in {pico.population}: A randomized controlled trial",
            "abstract": (
                f"Background: {pico.intervention} has been proposed as a treatment "
                f"for {pico.population}. "
                f"Methods: This RCT enrolled {random.randint(50, 500)} participants "
                f"randomized to {pico.intervention} (n={random.randint(25, 250)}) "
                f"or {pico.comparison} (n={random.randint(25, 250)}). "
                f"Primary outcome was {pico.outcome} at "
                f"{random.choice([12, 24, 52])} weeks. "
                f"Results: Mean {pico.outcome} was {random.uniform(5, 10):.1f} "
                f"(SD {random.uniform(1, 3):.1f}) vs "
                f"{random.uniform(6, 12):.1f} (SD {random.uniform(1, 3):.1f}). "
                f"Conclusion: {pico.intervention} significantly improved outcomes."
            ),
            "year": year,
            "authors": [f"{first_authors[i % len(first_authors)]} A", "Co-author B"]
        })

    return studies


# ── Entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # ── CONFIGURE YOUR META-ANALYSIS HERE ──────────────────────
    MY_PICO = PICO(
        population="Type 2 diabetes mellitus patients with cardiovascular risk",
        intervention="SGLT2 inhibitors (empagliflozin, dapagliflozin, canagliflozin)",
        comparison="Placebo",
        outcome="Major adverse cardiovascular events (MACE: CV death, non-fatal MI, non-fatal stroke)",
        study_design="Randomized controlled trial",
        time_frame="≥12 weeks follow-up"
    )

    INCLUSION = [
        "Randomized controlled trials (RCT)",
        "Adult patients (≥18 years) with T2DM",
        "SGLT2 inhibitor as intervention",
        "Placebo or usual care as comparator",
        "Report MACE or its components",
        "Follow-up ≥12 weeks"
    ]

    EXCLUSION = [
        "Non-randomized studies",
        "Animal studies or in vitro",
        "Type 1 diabetes mellitus",
        "Conference abstracts without full data",
        "Duplicate publications"
    ]

    project = run_meta_analysis(
        title="SGLT2 Inhibitors and Major Adverse Cardiovascular Events in "
              "Type 2 Diabetes: A Systematic Review and Meta-Analysis",
        pico=MY_PICO,
        inclusion_criteria=INCLUSION,
        exclusion_criteria=EXCLUSION,
        rob_tool="RoB2",
        target_journal="PLOS ONE",
        protocol_doi="CRD42025XXXXXX",   # Replace with your PROSPERO ID
        demo_mode=True                    # Set False to use real PubMed
    )
