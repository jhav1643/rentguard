from langchain_core.tools import tool

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.common.clause_splitter import split_lease
from services.classifier_service.serving.Inferences import predict_risk
from services.ingestion.retrieval import retrieve

@tool
def extract_clauses(lease_text: str) -> list[str]:
    """
    Extracts clauses from a lease text.
    Args:
        lease_text: The full text of the lease.
    Returns:
        A list of clauses.
    """
    return split_lease(lease_text)

@tool
def classify_clause_risk(clause_text: str, monthly_rent_bracket: str) -> dict:
    """
    Classifies the risk of a clause based on its text and the monthly rent bracket.
    Args:
        clause_text: The text of the clause.
        monthly_rent_bracket: The monthly rent bracket (e.g., "low", "medium", "high").
    Returns:
        A dictionary with the risk classification and associated score.
    """
    return predict_risk(clause_text, monthly_rent_bracket)

@tool
def retrieve_law(query: str, jurisdiction: str, k: int = 3) -> list[dict]:
    """
    Retrieves relevant legal documents based on a query and jurisdiction.
    Args:
        query: The search query.
        jurisdiction: The jurisdiction to filter the results.
        k: The number of top results to return.
    Returns:
        A list of dictionaries with text, source, jurisdiction, and score for each retrieved document.
    """
    return retrieve(query, jurisdiction, k)

ALL_TOOLS = [extract_clauses, classify_clause_risk, retrieve_law ]

if __name__ == "__main__":
    print("Registered tools:\n")
    for tool in ALL_TOOLS:
        print(f"- {tool.name}: {tool.description[:80]}")