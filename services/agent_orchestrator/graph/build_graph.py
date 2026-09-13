from langgraph.graph import END, StateGraph

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.agent_orchestrator.graph.nodes import (
    check_rent_bracket_node,
    citation_check_node,
    classify_clauses_node,
    draft_communication_node,
    extract_clauses_node,
    generate_explanation_node,
    retrieve_grounding_node,
)

from services.agent_orchestrator.graph.state import LeaseAnalysisState

def route_after_extraction(state: LeaseAnalysisState) -> str:
    return "end" if state.get("error") else "continue"

def route_after_rent_check(state: LeaseAnalysisState) -> str:
    return "end" if state.get("needs_user_input") else "continue"

def build_lease_analysis_graph():
    graph = StateGraph(LeaseAnalysisState)

    graph.add_node("extract_clauses", extract_clauses_node)
    graph.add_node("check_rent_bracket", check_rent_bracket_node)
    graph.add_node("classify_clauses", classify_clauses_node)
    graph.add_node("retrieve_grounding", retrieve_grounding_node)
    graph.add_node("generate_explanations", generate_explanation_node)
    graph.add_node("citation_check", citation_check_node)
    graph.add_node("draft_communication_node", draft_communication_node)

    graph.set_entry_point("extract_clauses")

    graph.add_conditional_edges(
        "extract_clauses",
        route_after_extraction,
        {"continue": "check_rent_bracket", "end": END},
    )
 
    graph.add_conditional_edges(
        "check_rent_bracket",
        route_after_rent_check,
        {"continue": "classify_clauses", "end": END},
    )
 
    graph.add_edge("classify_clauses", "retrieve_grounding")
    graph.add_edge("retrieve_grounding", "generate_explanations")
    graph.add_edge("generate_explanations", "citation_check")
    graph.add_edge("citation_check", "draft_communication_node")
    graph.add_edge("draft_communication_node", END)
 
    return graph.compile()

 
if __name__ == "__main__":
    app = build_lease_analysis_graph()
    print("Graph compiled successfully.")
    try:
        print(app.get_graph().draw_ascii())
    except Exception:
        print("(ASCII graph rendering unavailable -- install 'grandalf' for this, optional)")