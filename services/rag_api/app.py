import os
import logging

from flask import Flask, request, jsonify
from prometheus_flask_exporter import PrometheusMetrics
from prometheus_client import Counter, Histogram

from services.ingestion.retrieval import retrieve

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Auto-exposes /metrics and default HTTP metrics.
metrics = PrometheusMetrics(app)
metrics.info("rag_api_info", "RentGuard RAG API", version="1.0.0")

# ---------------------------------------------------------------------------
# Custom Prometheus metrics
# ---------------------------------------------------------------------------
RETRIEVAL_LATENCY = Histogram(
    "rag_retrieval_latency_seconds",
    "Retrieval latency in seconds",
    buckets=[0.1, 0.25, 0.5, 1, 2, 5, 10],
)

RETRIEVAL_EMPTY = Counter(
    "rag_retrieval_empty_total",
    "Number of retrievals that returned zero chunks",
)

LLM_TOKENS = Counter(
    "llm_tokens_total",
    "LLM tokens used",
    ["model", "type"],
)

CITATION_CHECK = Counter(
    "citation_check_total",
    "Citation check results",
    ["status"],
)

RAG_REQUESTS = Counter(
    "rag_requests_total",
    "RAG API requests",
    ["endpoint", "status"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def normalize_jurisdiction(jurisdiction):
    if jurisdiction is None:
        return None
    value = str(jurisdiction).strip().lower()
    return value or None


def retrieve_docs(query, jurisdiction=None):
    jur = normalize_jurisdiction(jurisdiction)

    with RETRIEVAL_LATENCY.time():
        docs = retrieve(query=query, jurisdiction=jur)

    if not docs:
        RETRIEVAL_EMPTY.inc()
        logger.warning("No matches found for jurisdiction=%r", jur)

    return docs or []


def check_citations(answer, docs):
    if not docs:
        CITATION_CHECK.labels(status="fail").inc()
        return False

    answer_lower = (answer or "").lower()
    ok = False
    for doc in docs:
        metadata = getattr(doc, "metadata", {}) or {}
        source = str(metadata.get("source", "")).lower()
        title = str(metadata.get("title", "")).lower()
        if (source and source in answer_lower) or (title and title in answer_lower):
            ok = True
            break

    CITATION_CHECK.labels(status="pass" if ok else "fail").inc()
    return ok


def generate_answer(query, docs):
    context = "\n\n".join(
        getattr(doc, "page_content", str(doc)) for doc in docs[:5]
    )
    model = os.getenv("RAG_LLM_MODEL", "gpt-4o-mini")

    prompt = (
        "Answer the question using only the context below.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {query}\n"
        "Answer:"
    )

    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage

        llm = ChatOpenAI(model=model, temperature=0)
        response = llm.invoke([HumanMessage(content=prompt)])

        answer = (
            response.content
            if hasattr(response, "content")
            else str(response)
        )

        usage = (
            getattr(response, "usage_metadata", None)
            or getattr(response, "response_metadata", {}).get("token_usage", {})
        )

        if usage:
            LLM_TOKENS.labels(model=model, type="prompt").inc(
                usage.get("prompt_tokens", 0)
            )
            LLM_TOKENS.labels(model=model, type="completion").inc(
                usage.get("completion_tokens", 0)
            )
        else:
            LLM_TOKENS.labels(model=model, type="prompt").inc(len(prompt.split()))
            LLM_TOKENS.labels(model=model, type="completion").inc(len(answer.split()))

        return answer

    except Exception as exc:
        logger.exception("LLM generation failed: %s", exc)
        return context or "No relevant context found."


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/query", methods=["POST"])
def query():
    data = request.get_json(silent=True) or {}
    question = data.get("question") or data.get("query")
    jurisdiction = data.get("jurisdiction")

    if not question:
        RAG_REQUESTS.labels(endpoint="/query", status="400").inc()
        return jsonify({"error": "question is required"}), 400

    try:
        docs = retrieve_docs(question, jurisdiction)
        answer = generate_answer(question, docs)
        citation_ok = check_citations(answer, docs)

        sources = []
        for doc in docs:
            metadata = getattr(doc, "metadata", {}) or {}
            sources.append(
                {
                    "source": metadata.get("source", ""),
                    "title": metadata.get("title", ""),
                    "page": metadata.get("page"),
                    "score": metadata.get("score"),
                }
            )

        RAG_REQUESTS.labels(endpoint="/query", status="200").inc()
        return (
            jsonify(
                {
                    "answer": answer,
                    "sources": sources,
                    "citation_check": "pass" if citation_ok else "fail",
                    "jurisdiction": normalize_jurisdiction(jurisdiction),
                }
            ),
            200,
        )

    except Exception as exc:
        logger.exception("query failed")
        RAG_REQUESTS.labels(endpoint="/query", status="500").inc()
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))