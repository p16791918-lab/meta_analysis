"""
Pydantic data models for the meta-analysis pipeline.
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


class StudyDesign(str, Enum):
    RCT = "RCT"
    COHORT = "cohort"
    CASE_CONTROL = "case-control"
    CROSS_SECTIONAL = "cross-sectional"


class OutcomeType(str, Enum):
    CONTINUOUS = "continuous"
    BINARY = "binary"
    TIME_TO_EVENT = "time-to-event"


class RoBLevel(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class PICO:
    population: str
    intervention: str
    comparison: str
    outcome: str
    study_design: Optional[str] = None
    time_frame: Optional[str] = None


@dataclass
class SearchResult:
    pico: PICO
    mesh_terms: List[str]
    pubmed_query: str
    cochrane_query: str
    embase_query: str
    total_hits: int
    studies: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ScreeningDecision:
    pmid: str
    title: str
    authors: str
    year: int
    phase1_decision: str  # include | exclude | uncertain
    phase1_reason: str
    phase2_decision: Optional[str] = None
    phase2_reason: Optional[str] = None
    rob_tool: Optional[str] = None
    rob_domains: Optional[Dict] = None
    rob_overall: Optional[RoBLevel] = None


@dataclass
class OutcomeData:
    name: str
    outcome_type: OutcomeType
    # Continuous
    intervention_mean: Optional[float] = None
    intervention_sd: Optional[float] = None
    intervention_n: Optional[int] = None
    control_mean: Optional[float] = None
    control_sd: Optional[float] = None
    control_n: Optional[int] = None
    # Binary
    intervention_events: Optional[int] = None
    intervention_total: Optional[int] = None
    control_events: Optional[int] = None
    control_total: Optional[int] = None
    # Time-to-event
    hr: Optional[float] = None
    hr_ci_low: Optional[float] = None
    hr_ci_high: Optional[float] = None


@dataclass
class ExtractedStudy:
    study_id: str  # AuthorYear format
    pmid: str
    design: StudyDesign
    n_total: int
    n_intervention: int
    n_control: int
    follow_up_weeks: Optional[float]
    country: Optional[str]
    primary_outcome: OutcomeData
    secondary_outcomes: List[OutcomeData] = field(default_factory=list)
    subgroups: Dict[str, Any] = field(default_factory=dict)
    confounders_adjusted: List[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class AnalysisResult:
    effect_measure: str  # OR, RR, MD, SMD, HR
    model: str           # fixed, random
    pooled_estimate: float
    ci_low: float
    ci_high: float
    p_value: float
    i_squared: float
    tau_squared: float
    q_statistic: float
    q_p_value: float
    n_studies: int
    n_participants: int
    prediction_interval_low: Optional[float] = None
    prediction_interval_high: Optional[float] = None
    egger_p: Optional[float] = None
    r_code: str = ""
    forest_plot_path: Optional[str] = None
    funnel_plot_path: Optional[str] = None


@dataclass
class MetaAnalysisProject:
    """Master project object passed between agents."""
    title: str
    pico: PICO
    protocol_doi: Optional[str] = None  # PROSPERO
    search_results: Optional[SearchResult] = None
    included_studies: List[ScreeningDecision] = field(default_factory=list)
    extracted_data: List[ExtractedStudy] = field(default_factory=list)
    analysis: Optional[AnalysisResult] = None
    manuscript_sections: Dict[str, str] = field(default_factory=dict)
    target_journal: str = "PLOS ONE"
