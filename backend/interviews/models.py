"""Pydantic models for Interview mode."""

from pydantic import BaseModel


class InterviewTestCase(BaseModel):
    input: str
    expected_output: str


class InterviewChallenge(BaseModel):
    """A single challenge within an interview room."""
    id: str
    title: str
    description: str
    category: str  # coding, frontend, system_design
    starter_code: str | None = None
    solution_code: str | None = None
    test_cases: list[InterviewTestCase] | None = None
    reference_html: str | None = None
    sort_order: int = 0


class InterviewConfig(BaseModel):
    """Room-level configuration set by interviewer."""
    time_limit_minutes: int = 45
    allowed_models: list[str] | None = None  # None = all allowed
    max_token_budget: int | None = None  # None = unlimited
    show_test_results_to_candidate: bool = True


class InterviewRoom(BaseModel):
    """An interview room created by an interviewer."""
    id: str
    created_by: str  # interviewer name / email
    title: str
    company_name: str = ""
    invite_code: str
    config: InterviewConfig = InterviewConfig()
    challenges: list[InterviewChallenge] = []
    status: str = "pending"  # pending, active, completed
    created_at: float = 0.0


class InterviewTurn(BaseModel):
    """A single prompt-response turn within an interview session."""
    turn_number: int
    prompt_text: str
    response_text: str = ""
    generated_code: str = ""
    prompt_tokens: int = 0
    response_tokens: int = 0
    timestamp: float = 0.0


class InterviewSession(BaseModel):
    """A candidate's attempt at a single challenge in an interview."""
    id: str
    room_id: str
    challenge_id: str
    candidate_name: str
    status: str = "active"  # active, completed
    started_at: float = 0.0
    completed_at: float | None = None
    total_tokens: int = 0
    total_turns: int = 0
    accuracy: float = 0.0
    composite_score: int = 0
    turns: list[InterviewTurn] = []
    final_code: str = ""


# ---------------------------------------------------------------------------
# Request / Response schemas (used by the router)
# ---------------------------------------------------------------------------


class CreateRoomRequest(BaseModel):
    created_by: str
    title: str
    company_name: str = ""
    config: InterviewConfig = InterviewConfig()


class AddChallengeRequest(BaseModel):
    title: str
    description: str
    category: str  # coding, frontend, system_design
    starter_code: str | None = None
    solution_code: str | None = None
    test_cases: list[InterviewTestCase] | None = None
    reference_html: str | None = None


class UpdateChallengeRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    category: str | None = None
    starter_code: str | None = None
    solution_code: str | None = None
    test_cases: list[InterviewTestCase] | None = None
    reference_html: str | None = None


class UpdateRoomRequest(BaseModel):
    title: str | None = None
    company_name: str | None = None
    config: InterviewConfig | None = None


class StartSessionRequest(BaseModel):
    candidate_name: str
    challenge_id: str


class SubmitPromptRequest(BaseModel):
    prompt: str
    model: str | None = None
