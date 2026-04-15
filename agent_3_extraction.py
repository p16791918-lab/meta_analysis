"""
Agent 3: Data Extraction Agent
- Extracts quantitative data from included studies
- Handles continuous and binary outcomes
- Standardizes units and effect measures
"""
import json
import anthropic
from typing import List, Dict
from shared.prompts import EXTRACTION_AGENT_PROMPT
from shared.models import ExtractedStudy, OutcomeData, OutcomeType, StudyDesign


def extract_data(
    included_studies: List[Dict],
    primary_outcome_name: str,
    outcome_type: str = "continuous",
    secondary_outcomes: List[str] = None
) -> List[ExtractedStudy]:
    """
    Extract quantitative data from included studies.
    
    Args:
        included_studies: List of study dicts with abstract/full-text
        primary_outcome_name: e.g. "HbA1c change from baseline"
        outcome_type: "continuous" | "binary" | "time-to-event"
        secondary_outcomes: list of secondary outcome names
    
    Returns:
        List[ExtractedStudy]
    """
    client = anthropic.Anthropic()
    extracted = []

    if secondary_outcomes is None:
        secondary_outcomes = []

    print(f"[Agent 3: Extraction] Extracting data from {len(included_studies)} studies...")

    for idx, study in enumerate(included_studies):
        user_message = f"""
        Extract all quantitative data from this study for a meta-analysis.

        PRIMARY OUTCOME: {primary_outcome_name} ({outcome_type})
        SECONDARY OUTCOMES: {', '.join(secondary_outcomes) if secondary_outcomes else 'None specified'}

        STUDY TEXT:
        {json.dumps(study, ensure_ascii=False, indent=2)}

        Return ONLY a JSON object:
        {{
          "study_id": "LastnameYear",
          "pmid": "...",
          "design": "RCT|cohort|case-control|cross-sectional",
          "n_total": integer,
          "n_intervention": integer,
          "n_control": integer,
          "follow_up_weeks": number or null,
          "country": "...",
          "primary_outcome": {{
            "name": "...",
            "type": "continuous|binary|time-to-event",
            "intervention_mean": number or null,
            "intervention_sd": number or null,
            "intervention_n": integer or null,
            "control_mean": number or null,
            "control_sd": number or null,
            "control_n": integer or null,
            "intervention_events": integer or null,
            "intervention_total": integer or null,
            "control_events": integer or null,
            "control_total": integer or null,
            "hr": number or null,
            "hr_ci_low": number or null,
            "hr_ci_high": number or null
          }},
          "secondary_outcomes": [],
          "confounders_adjusted": [],
          "notes": "any data quality flags"
        }}

        If data is missing, use null. Do NOT fabricate numbers.
        Return ONLY JSON.
        """

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            system=EXTRACTION_AGENT_PROMPT,
            messages=[{"role": "user", "content": user_message}]
        )

        raw = response.content[0].text.strip()
        clean = raw.replace("```json", "").replace("```", "").strip()

        try:
            d = json.loads(clean)

            # Parse primary outcome
            po = d.get("primary_outcome", {})
            otype_map = {
                "continuous": OutcomeType.CONTINUOUS,
                "binary": OutcomeType.BINARY,
                "time-to-event": OutcomeType.TIME_TO_EVENT
            }
            primary = OutcomeData(
                name=po.get("name", primary_outcome_name),
                outcome_type=otype_map.get(po.get("type", outcome_type), OutcomeType.CONTINUOUS),
                intervention_mean=po.get("intervention_mean"),
                intervention_sd=po.get("intervention_sd"),
                intervention_n=po.get("intervention_n"),
                control_mean=po.get("control_mean"),
                control_sd=po.get("control_sd"),
                control_n=po.get("control_n"),
                intervention_events=po.get("intervention_events"),
                intervention_total=po.get("intervention_total"),
                control_events=po.get("control_events"),
                control_total=po.get("control_total"),
                hr=po.get("hr"),
                hr_ci_low=po.get("hr_ci_low"),
                hr_ci_high=po.get("hr_ci_high"),
            )

            design_map = {
                "RCT": StudyDesign.RCT,
                "cohort": StudyDesign.COHORT,
                "case-control": StudyDesign.CASE_CONTROL,
                "cross-sectional": StudyDesign.CROSS_SECTIONAL
            }

            study_obj = ExtractedStudy(
                study_id=d.get("study_id", f"Study{idx+1}"),
                pmid=d.get("pmid", study.get("pmid", "")),
                design=design_map.get(d.get("design", "RCT"), StudyDesign.RCT),
                n_total=d.get("n_total", 0),
                n_intervention=d.get("n_intervention", 0),
                n_control=d.get("n_control", 0),
                follow_up_weeks=d.get("follow_up_weeks"),
                country=d.get("country"),
                primary_outcome=primary,
                secondary_outcomes=[],
                confounders_adjusted=d.get("confounders_adjusted", []),
                notes=d.get("notes", "")
            )
            extracted.append(study_obj)
            print(f"[Agent 3: Extraction] ({idx+1}/{len(included_studies)}) {study_obj.study_id} ✓")

        except (json.JSONDecodeError, KeyError) as e:
            print(f"[Agent 3: Extraction] ⚠ Error parsing study {idx+1}: {e}")

    print(f"[Agent 3: Extraction] ✓ Extracted {len(extracted)}/{len(included_studies)} studies")
    return extracted


def to_r_dataframe(studies: List[ExtractedStudy]) -> str:
    """
    Convert extracted studies to R data.frame code for metafor.
    Handles both continuous (mean/SD) and binary (events/total) outcomes.
    """
    lines = ["# Auto-generated by Agent 3: Data Extraction", "library(metafor)", ""]
    lines.append("dat <- data.frame(")

    study_lines = []
    for s in studies:
        po = s.primary_outcome
        if po.outcome_type == OutcomeType.CONTINUOUS:
            study_lines.append(
                f'  list(study="{s.study_id}", n1i={s.n_intervention}, '
                f'm1i={po.intervention_mean}, sd1i={po.intervention_sd}, '
                f'n2i={s.n_control}, m2i={po.control_mean}, sd2i={po.control_sd})'
            )
        elif po.outcome_type == OutcomeType.BINARY:
            study_lines.append(
                f'  list(study="{s.study_id}", '
                f'ai={po.intervention_events}, n1i={po.intervention_total}, '
                f'ci={po.control_events}, n2i={po.control_total})'
            )

    lines.append(",\n".join(study_lines))
    lines.append(")")
    lines.append("\n# Convert to proper format")
    lines.append("dat <- do.call(rbind, lapply(dat, as.data.frame))")

    return "\n".join(lines)
