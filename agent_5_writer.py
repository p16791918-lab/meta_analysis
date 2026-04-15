"""
Agent 5: Manuscript Writing Agent
- Writes all IMRAD sections
- Follows PRISMA 2020 checklist
- Adapts to target journal style
- Outputs complete manuscript
"""
import anthropic
from typing import Dict, List, Optional
from shared.prompts import WRITER_AGENT_PROMPT
from shared.models import MetaAnalysisProject


JOURNAL_STYLES = {
    "JAMA": {"word_limit": 3000, "abstract_limit": 350, "style": "structured"},
    "NEJM": {"word_limit": 2700, "abstract_limit": 250, "style": "unstructured"},
    "Lancet": {"word_limit": 3000, "abstract_limit": 250, "style": "structured"},
    "BMJ": {"word_limit": 3500, "abstract_limit": 400, "style": "structured"},
    "PLOS ONE": {"word_limit": 9000, "abstract_limit": 300, "style": "structured"},
    "Systematic Reviews": {"word_limit": 8000, "abstract_limit": 350, "style": "structured"}
}


def write_section(
    section: str,
    context: Dict,
    client: anthropic.Anthropic,
    target_journal: str = "PLOS ONE"
) -> str:
    """Write a single manuscript section."""

    journal_info = JOURNAL_STYLES.get(target_journal, JOURNAL_STYLES["PLOS ONE"])

    section_prompts = {
        "abstract": f"""
            Write a structured abstract for this systematic review/meta-analysis.
            Target journal: {target_journal} (limit: {journal_info['abstract_limit']} words)
            
            Include these headings:
            Background, Objectives, Data Sources, Eligibility Criteria,
            Participants and Interventions, Study Appraisal, Synthesis Methods,
            Results, Limitations, Conclusions, PROSPERO Registration
            
            Context: {str(context)}
        """,

        "introduction": """
            Write the Introduction section (3-4 paragraphs):
            1. Clinical background and disease burden
            2. Current evidence gap and controversy
            3. Previous systematic reviews (if any) and their limitations
            4. Objectives of this meta-analysis (PICO statement)
            
            Context: """ + str(context),

        "methods": """
            Write a complete Methods section following PRISMA 2020.
            Include ALL of these subsections:
            2.1 Protocol and Registration
            2.2 Eligibility Criteria
            2.3 Information Sources
            2.4 Search Strategy (with example query in Appendix reference)
            2.5 Study Selection Process
            2.6 Data Collection Process
            2.7 Data Items
            2.8 Risk of Bias in Individual Studies
            2.9 Summary Measures
            2.10 Synthesis Methods (heterogeneity, model selection, subgroups)
            2.11 Publication Bias Assessment
            2.12 Certainty of Evidence (GRADE)
            
            Context: """ + str(context),

        "results": """
            Write the Results section. Include:
            3.1 Study Selection (PRISMA numbers from context)
            3.2 Study Characteristics (reference Table 1)
            3.3 Risk of Bias (reference Figure 2 or supplementary)
            3.4 Results of Syntheses:
                - Primary outcome: pooled estimate, CI, I², prediction interval
                - Subgroup analyses
                - Sensitivity analyses
            3.5 Publication Bias
            3.6 Certainty of Evidence (GRADE table reference)
            
            Context: """ + str(context),

        "discussion": """
            Write the Discussion section (4-5 paragraphs):
            1. Summary of main findings
            2. Comparison with previous literature/guidelines
            3. Biological/clinical plausibility
            4. Limitations:
               - Search limitations
               - Risk of bias in included studies
               - Heterogeneity sources
               - Publication bias
               - Applicability
            5. Implications for clinical practice and future research
            
            Context: """ + str(context),

        "conclusion": """
            Write a Conclusion paragraph (3-5 sentences):
            - Summarize key finding
            - State certainty of evidence
            - Clinical implication
            - Research gap
            
            Context: """ + str(context),
    }

    if section not in section_prompts:
        return f"[Section '{section}' not recognized]"

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=3000,
        system=WRITER_AGENT_PROMPT,
        messages=[{"role": "user", "content": section_prompts[section]}]
    )

    return response.content[0].text


def write_full_manuscript(project: MetaAnalysisProject) -> Dict[str, str]:
    """
    Write the complete manuscript for a meta-analysis project.
    Returns dict of section_name -> text.
    """
    client = anthropic.Anthropic()

    # Build context object for the writer
    context = {
        "title": project.title,
        "pico": {
            "P": project.pico.population,
            "I": project.pico.intervention,
            "C": project.pico.comparison,
            "O": project.pico.outcome
        },
        "n_included": len(project.included_studies),
        "n_total_retrieved": project.search_results.total_hits if project.search_results else "N/A",
        "prisma": getattr(project, 'prisma_numbers', {}),
        "analysis": {
            "results_narrative": project.manuscript_sections.get("results_narrative", ""),
            "grade": project.manuscript_sections.get("grade_table", "")
        },
        "rob_summary": getattr(project, 'rob_summary', {}),
        "target_journal": project.target_journal,
        "protocol_doi": project.protocol_doi
    }

    sections_order = ["abstract", "introduction", "methods", "results", "discussion", "conclusion"]
    manuscript = {}

    for section in sections_order:
        print(f"[Agent 5: Writer] Writing {section}...")
        text = write_section(section, context, client, project.target_journal)
        manuscript[section] = text
        print(f"[Agent 5: Writer] ✓ {section} ({len(text.split())} words)")

    return manuscript


def compile_manuscript(sections: Dict[str, str], project_title: str,
                       output_file: str = "manuscript.md") -> str:
    """Compile all sections into a single markdown manuscript."""

    lines = [
        f"# {project_title}",
        "",
        "---",
        "",
        "## Abstract",
        sections.get("abstract", ""),
        "",
        "---",
        "",
        "## 1. Introduction",
        sections.get("introduction", ""),
        "",
        "## 2. Methods",
        sections.get("methods", ""),
        "",
        "## 3. Results",
        sections.get("results", ""),
        "",
        "## 4. Discussion",
        sections.get("discussion", ""),
        "",
        "## 5. Conclusion",
        sections.get("conclusion", ""),
        "",
        "---",
        "",
        "**Word count (approx):** " +
        str(sum(len(v.split()) for v in sections.values())),
        "",
        "*Generated by Meta-Analysis Agent System*"
    ]

    full_text = "\n".join(lines)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(full_text)

    print(f"[Agent 5: Writer] ✓ Manuscript saved to {output_file}")
    return full_text
