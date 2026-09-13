from typing import Optional, TypedDict

class LeaseAnalysisState(TypedDict, total=False):

    lease_text: str
    jurisdiction: str

    monthly_rent_bracket: Optional[str]
    needs_user_input:bool
    user_input_prompt: Optional[str]

    clauses: list[dict]

    clause_risk_results: list[dict]
    flagged_clauses: list[dict]

    retrieved_law: dict[int, list[dict]]
    explanations: list[dict]

    citation_check_passed: bool
    draft_communication: Optional[str]

    error: Optional[str]