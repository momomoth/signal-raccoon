from typing import List, Optional

from pydantic import BaseModel, Field


class CompanyInput(BaseModel):
    company: str = Field(..., description="Company name")
    website: str = Field("", description="Company website URL")
    linkedin: str = Field("", description="Company LinkedIn URL")


class Firmographics(BaseModel):
    name: Optional[str] = None
    industry: Optional[str] = None
    employee_count: Optional[str] = None
    revenue: Optional[str] = None
    funding_stage: Optional[str] = None
    technologies: List[str] = Field(default_factory=list)
    raw: dict = Field(default_factory=dict, description="Raw Apollo response")


class NewsSearchResult(BaseModel):
    title: str
    url: str
    snippet: str
    published_date: Optional[str] = None


class Article(BaseModel):
    title: Optional[str] = None
    url: str
    body: str
    publication_date: Optional[str] = None


class IntentSignal(BaseModel):
    signal_type: str = Field(
        ...,
        description=(
            "One of: breach_incident, regulatory_action, ciso_hire, cio_hire, "
            "major_ai_rollout, chief_ai_officer_hire, agentic_workflow_adoption, "
            "security_team_expansion, ai_expansion_initiative, ai_blog_post, "
            "thought_leadership, generic_ai_mention"
        ),
    )
    title: str
    url: str
    evidence: str
    severity: int = Field(..., ge=1, le=10)
    date: Optional[str] = Field(None, description="Article publication date in ISO format if available")


class CategoryScore(BaseModel):
    """Score for one firmographic dimension."""
    category: str
    score: int
    max_possible: int = 10
    evidence: List[str] = Field(default_factory=list)
    weight: float
    data_quality: str


class FirmographicProfile(BaseModel):
    """Categorical assessment of a company's structural SSPM fit."""
    categories: List[CategoryScore]
    composite_score: float
    data_quality: str


class IntentAnalysisResult(BaseModel):
    """What the LLM returns from signal detection."""
    signals: List[IntentSignal]
    raw_intent_score: int = Field(..., ge=1, le=10)
    reasoning: str


class ScoringConfig(BaseModel):
    """Weights and thresholds for the consolidation layer."""
    signal_weight: float = 0.60
    firmo_weight: float = 0.40
    recency_window_days: int = 30
    recency_floor: float = 0.70
    recency_ceiling: float = 1.30
    count_floor: float = 0.80
    count_ceiling: float = 1.20
    firmo_max_standalone_tier: str = "okay"


class ConsolidatedReport(BaseModel):
    """Final output returned by /analyze-intent."""
    company: str
    final_score: float
    fit_tier: str
    raw_intent_score: Optional[int] = None
    firmographic_score: float = 0.0
    intent_signals: List[IntentSignal] = Field(default_factory=list)
    firmographic_profile: Optional[FirmographicProfile] = None
    thesis: str = ""
    outreach_stance: str = "insufficient"
    data_flags: List[str] = Field(default_factory=list)
    reasoning: Optional[str] = None
    summary: Optional[str] = None
    articles_considered: int = 0
    errors: List[str] = Field(default_factory=list)
