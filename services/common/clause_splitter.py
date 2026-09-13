import re
import json
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

# Configurable via environment or constants
MIN_CONFIDENT_MATCHES = 2   # was 3, changed to 2
MIN_CLAUSE_WORDS = 5
MAX_CLAUSE_WORDS = 300     # was 30, corrected to 300

CLAUSE_START_PATTERNS = [
    re.compile(r"^\s*(\d{1,2})\.\s+(?=\S)", re.MULTILINE),
    re.compile(r"^\s*Clause\s+(\d{1,2})[:.]\s*", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\s*(\d{1,2})\)\s+(?=\S)", re.MULTILINE),
]

def _split_on_pattern(text: str, pattern: re.Pattern) -> list[str]:
    matches = list(pattern.finditer(text))
    if len(matches) < MIN_CONFIDENT_MATCHES:
        return []

    segments = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        segment = text[start:end].strip()
        if segment:
            segments.append(segment)
    return segments

def split_clauses(text: str) -> Optional[list[str]]:
    """Try each pattern; return the first one that yields enough matches."""
    for pattern in CLAUSE_START_PATTERNS:
        segments = _split_on_pattern(text, pattern)
        if segments:
            return segments
    return None

def llm_assisted_split(text: str) -> list[str]:
    """Use the LLM to split text into clauses when rule-based fails."""
    try:
        # Import here to avoid circular dependency and only when needed
        from services.agent_orchestrator.llm import get_llm

        llm = get_llm()
        prompt = (
            "You are given the text of a lease agreement. Split it into individual clauses.\n"
            "Return a JSON list of strings, each string being a single clause. Preserve the original text exactly.\n\n"
            "Text:\n"
            f"{text}\n"
        )
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)

        # Try to parse as JSON list
        try:
            clauses = json.loads(content)
            if isinstance(clauses, list):
                clauses = [c.strip() for c in clauses if c.strip()]
                if clauses:
                    return clauses
        except json.JSONDecodeError:
            # Fallback: try splitting by newlines if LLM didn't return clean JSON
            lines = [line.strip() for line in content.split("\n") if line.strip()]
            if len(lines) > 1:
                return lines

    except Exception as e:
        logger.error("LLM-assisted splitting failed: %s", e)

    # If all else fails, return the whole text as one clause
    logger.warning("LLM fallback also failed; returning full text as a single clause.")
    return [text.strip()] if text.strip() else []

def validate_clause_lengths(clauses: list[str]) -> list[dict]:
    results = []
    for i, clause_text in enumerate(clauses):
        word_count = len(clause_text.split())
        needs_review = word_count < MIN_CLAUSE_WORDS or word_count > MAX_CLAUSE_WORDS
        results.append({
            "clause_index": i,
            "clause_text": clause_text,
            "word_count": word_count,
            "needs_review": needs_review,
            "split_method": None,  # filled later
        })
    return results

def split_lease(text: str) -> list[dict]:
    if not text or not text.strip():
        raise ValueError("Input text is empty -- nothing to split.")

    segments = split_clauses(text)
    method = "rule_based"

    if segments is None:
        segments = llm_assisted_split(text)
        method = "llm_fallback"

    clauses = validate_clause_lengths(segments)
    for clause in clauses:
        clause["split_method"] = method

    flagged_count = sum(1 for c in clauses if c["needs_review"])
    logger.info("Split into %d clause(s) via %s. %d flagged for length review.",
                len(clauses), method, flagged_count)

    return clauses

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sample_lease = """
1. Security Deposit: The tenant shall pay a security deposit of 3 months' rent, refundable within 30 days of vacating.

2. Notice Period: Either party may terminate this agreement with 30 days' written notice.

3. Maintenance: Landlord shall be responsible for structural repairs, tenant for minor upkeep.
"""
    result = split_lease(sample_lease)
    for clause in result:
        print(clause)