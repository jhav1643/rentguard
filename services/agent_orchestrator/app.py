import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.agent_orchestrator.graph.build_graph import build_lease_analysis_graph

app = build_lease_analysis_graph()

sample_lease = """
1. Security Deposit: The tenant shall pay a security deposit of 10 months' rent, non-refundable under any circumstances.

2. Notice Period: Landlord may terminate the tenancy at any time without notice if he deems it necessary.
"""

# First call -- rent bracket not yet known
result = app.invoke({"lease_text": sample_lease, "jurisdiction": "delhi"})
print(result.get("user_input_prompt"))

# Second call -- with the answer
result = app.invoke({
    "lease_text": sample_lease,
    "jurisdiction": "delhi",
    "monthly_rent_bracket": "above_3500",
})
print(result["clause_risk_results"])
print(result["explanations"])
print(result["draft_communication"])