import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.agent_orchestrator.llm import get_llm
from services.classifier_service.serving.Inferences import predict_risk
from services.common.clause_splitter import split_lease
from services.ingestion.retrieval import retrieve


def extract_clauses_node(state: dict) -> dict:
    try:
        clauses = split_lease(state["lease_text"])
    except ValueError as e:
        return {"error": f"Could not extract clauses: {e}"}

    if not clauses:
        return {"error": "No clauses could be extracted from the lease text."}

    return {"clauses": clauses}


def check_rent_bracket_node(state: dict) -> dict:
    if state.get("monthly_rent_bracket") in ("le_3500", "above_3500"):
        return {"needs_user_input": False}

    return {
        "needs_user_input": True,
        "user_input_prompt": (
            "What is your monthly rent? This determines which legal "
            "protections apply to your tenancy (Delhi Rent Control Act "
            "provisions only apply to rents of Rs 3,500/month or below)."
        ),
    }


def classify_clauses_node(state: dict) -> dict:
    bracket = state.get("monthly_rent_bracket")
    results = []

    for clause in state["clauses"]:
        try:
            prediction = predict_risk(clause["clause_text"], bracket)
        except Exception as e:
            prediction = {"risk_label": "unknown", "confidence": None, "error": str(e)}

        results.append({**clause, **prediction})

    flagged = [c for c in results if c.get("risk_label") in ("Caution", "High Risk")]

    return {"clause_risk_results": results, "flagged_clauses": flagged}


def retrieve_grounding_node(state: dict) -> dict:
    flagged_clauses = state.get("flagged_clauses", [])
    jurisdiction = state["jurisdiction"]
    retrieved = {}

    for clause in flagged_clauses:
        idx = clause["clause_index"]  # <-- use the original clause index
        query = clause["clause_text"][:200]

        try:
            results = retrieve(query=query, jurisdiction=jurisdiction, k=3)
        except Exception as e:
            results = {"error": f"Retrieval failed for clause {idx}: {e}"}

        retrieved[idx] = results

    return {"retrieved_law": retrieved}


def generate_explanation_node(state: dict) -> dict:
    flagged_clauses = state.get("flagged_clauses", [])
    llm = get_llm()
    explanations = []

    for clause in flagged_clauses:
        idx = clause["clause_index"]  # <-- use the original clause index
        context_chunks = state["retrieved_law"].get(idx, [])
        context_text = "\n\n".join(c["text"] for c in context_chunks) or "No supporting legal text found."

        prompt = (
            f"A lease clause was flagged as '{clause['risk_label']}'.\n\n"
            f"Clause: \"{clause['clause_text']}\"\n\n"
            f"Relevant legal text:\n{context_text}\n\n"
            f"In 2-3 plain-language sentences, explain to a tenant why this "
            f"clause was flagged, citing the legal text above ONLY if it "
            f"actually supports the explanation. If the legal text doesn't "
            f"clearly apply, explain the risk in terms of market convention "
            f"instead and say so explicitly."
        )

        response = llm.invoke(prompt)

        explanations.append(
            {
                "clause_index": idx,
                "clause_text": clause["clause_text"],
                "risk_label": clause["risk_label"],
                "explanation_text": response.content,
                "context_used": context_chunks,
            }
        )

    return {"explanations": explanations}


def citation_check_node(state: dict) -> dict:
    """Anti-hallucination guard: verifies any 'Section N' style
    citation mentioned in an explanation actually appears in the
    retrieved text it was supposedly grounded in. A simple
    substring-presence check, deliberately conservative -- a real
    citation should appear near-verbatim in the source it quotes.
    """
    all_passed = True

    for explanation in state["explanations"]:
        combined_context = " ".join(c["text"] for c in explanation["context_used"])
        cited_sections = re.findall(r"Section\s+\d+", explanation["explanation_text"], re.IGNORECASE)

        for citation in cited_sections:
            if citation.lower() not in combined_context.lower():
                explanation["explanation_text"] += (
                    f"\n\n[NOTE: citation '{citation}' could not be verified "
                    f"against retrieved sources and may be inaccurate.]"
                )
                all_passed = False

    return {"citation_check_passed": all_passed}


def draft_communication_node(state: dict) -> dict:
    """Drafts a negotiation email to the landlord referencing flagged
    clauses. Only runs if there's at least one flagged clause worth
    raising -- returns None otherwise rather than drafting an empty
    or pointless email.
    """
    if not state.get("flagged_clauses"):
        return {"draft_communication": None}

    llm = get_llm()

    summary_points = "\n".join(
        f"- {e['clause_text'][:150]}... ({e['risk_label']}): {e['explanation_text']}"
        for e in state["explanations"]
    )

    prompt = (
        f"Draft a polite, professional email from a tenant to their landlord, "
        f"raising the following concerns about their lease agreement:\n\n"
        f"{summary_points}\n\n"
        f"The tone should be respectful and aim to open a conversation, not "
        f"accuse the landlord of wrongdoing. Keep it concise."
    )

    response = llm.invoke(prompt)
    return {"draft_communication": response.content}