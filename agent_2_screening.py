"""
Agent 2: Screening Agent
- Phase 1: Title/Abstract screening
- Phase 2: Full-text screening
- Risk of Bias assessment (RoB 2 / NOS)
- PRISMA flowchart numbers
"""
import json
import anthropic
from typing import List, Dict
from shared.prompts import SCREENING_AGENT_PROMPT
from shared.models import ScreeningDecision, RoBLevel, PICO


def screen_studies(
    studies: List[Dict],
    pico: PICO,
    inclusion_criteria: List[str],
    exclusion_criteria: List[str],
    rob_tool: str = "RoB2"
) -> Dict:
    """
    Screen a list of studies and return PRISMA numbers + decisions.
    
    Returns:
        {
            "decisions": List[ScreeningDecision],
            "prisma": { phase1_excluded, phase2_excluded, included_final },
            "rob_summary": { low, moderate, high }
        }
    """
    client = anthropic.Anthropic()
    decisions = []

    # Batch studies into groups of 10 to reduce API calls
    batch_size = 10
    batches = [studies[i:i+batch_size] for i in range(0, len(studies), batch_size)]

    print(f"[Agent 2: Screening] Processing {len(studies)} studies in {len(batches)} batches...")

    for batch_idx, batch in enumerate(batches):
        studies_text = json.dumps(batch, indent=2, ensure_ascii=False)

        user_message = f"""
        Screen these studies for a meta-analysis.

        PICO:
        P: {pico.population}
        I: {pico.intervention}
        C: {pico.comparison}
        O: {pico.outcome}

        INCLUSION CRITERIA:
        {chr(10).join(f'- {c}' for c in inclusion_criteria)}

        EXCLUSION CRITERIA:
        {chr(10).join(f'- {c}' for c in exclusion_criteria)}

        ROB TOOL: {rob_tool}

        STUDIES (batch {batch_idx+1}):
        {studies_text}

        For EACH study, return a JSON array of decisions:
        [
          {{
            "pmid": "...",
            "title": "...",
            "phase1_decision": "include|exclude|uncertain",
            "phase1_reason": "brief reason",
            "phase2_decision": "include|exclude|pending_full_text",
            "phase2_reason": "brief reason",
            "rob_overall": "low|moderate|high|critical|not_applicable"
          }},
          ...
        ]

        Return ONLY the JSON array. No explanations.
        """

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=3000,
            system=SCREENING_AGENT_PROMPT,
            messages=[{"role": "user", "content": user_message}]
        )

        raw = response.content[0].text.strip()
        clean = raw.replace("```json", "").replace("```", "").strip()

        try:
            batch_decisions = json.loads(clean)
            for d in batch_decisions:
                rob_map = {
                    "low": RoBLevel.LOW,
                    "moderate": RoBLevel.MODERATE,
                    "high": RoBLevel.HIGH,
                    "critical": RoBLevel.CRITICAL
                }
                decisions.append(ScreeningDecision(
                    pmid=d.get("pmid", ""),
                    title=d.get("title", ""),
                    authors="",
                    year=0,
                    phase1_decision=d.get("phase1_decision", "uncertain"),
                    phase1_reason=d.get("phase1_reason", ""),
                    phase2_decision=d.get("phase2_decision"),
                    phase2_reason=d.get("phase2_reason"),
                    rob_tool=rob_tool,
                    rob_overall=rob_map.get(d.get("rob_overall", ""), None)
                ))
        except json.JSONDecodeError as e:
            print(f"[Agent 2: Screening] ⚠ JSON parse error in batch {batch_idx+1}: {e}")

        print(f"[Agent 2: Screening] Batch {batch_idx+1}/{len(batches)} done")

    # PRISMA counts
    phase1_excluded = sum(1 for d in decisions if d.phase1_decision == "exclude")
    phase2_excluded = sum(1 for d in decisions
                         if d.phase1_decision != "exclude"
                         and d.phase2_decision == "exclude")
    included_final = sum(1 for d in decisions if d.phase2_decision == "include")

    rob_summary = {
        "low": sum(1 for d in decisions if d.rob_overall == RoBLevel.LOW),
        "moderate": sum(1 for d in decisions if d.rob_overall == RoBLevel.MODERATE),
        "high": sum(1 for d in decisions if d.rob_overall == RoBLevel.HIGH),
        "critical": sum(1 for d in decisions if d.rob_overall == RoBLevel.CRITICAL),
    }

    print(f"[Agent 2: Screening] ✓ Complete")
    print(f"  → Phase 1 excluded: {phase1_excluded}")
    print(f"  → Phase 2 excluded: {phase2_excluded}")
    print(f"  → Final included:   {included_final}")
    print(f"  → RoB: {rob_summary}")

    return {
        "decisions": decisions,
        "prisma": {
            "total_retrieved": len(studies),
            "phase1_excluded": phase1_excluded,
            "phase2_excluded": phase2_excluded,
            "included_final": included_final
        },
        "rob_summary": rob_summary
    }


def generate_prisma_text(prisma: Dict) -> str:
    """Generate PRISMA flow description for Methods section."""
    return f"""
PRISMA Flow:
- Records identified: {prisma['total_retrieved']}
- Records excluded (title/abstract): {prisma['phase1_excluded']}
- Full-text assessed: {prisma['total_retrieved'] - prisma['phase1_excluded']}
- Full-text excluded: {prisma['phase2_excluded']}
- Studies included in synthesis: {prisma['included_final']}
"""
