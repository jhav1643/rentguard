from flask import Flask, request, jsonify
from pathlib import Path
import sys
import importlib.util

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

retrieval_path = Path(__file__).resolve().parents[1] / "ingestion" / "retrieval.py"
spec = importlib.util.spec_from_file_location("retrieval_mod", retrieval_path)
if spec is None or spec.loader is None:
    raise ImportError(f"Could not load retrieval module from {retrieval_path}")

retrieval_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(retrieval_mod)

ALLOWED_JURISDICTIONS = retrieval_mod.ALLOWED_JURISDICTIONS
retrieve = retrieval_mod.retrieve


app = Flask(__name__)

@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200

@app.route("/jurisdictions", methods=["GET"])
def list_jurisdictions():
    return jsonify({"jurisdictions": list(ALLOWED_JURISDICTIONS)}), 200


@app.route("/retrieve", methods=["POST"])
def retrieve_chunks():
    data = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "No data provided."}), 400
    
    query = data.get("query", "")
    jurisdiction = data.get("jurisdiction")

    k = data.get("k", 5)

    if not query or not isinstance(query, str):
        return jsonify({"error": "No query provided."}), 400

    if not jurisdiction or not isinstance(jurisdiction, str) or jurisdiction not in ALLOWED_JURISDICTIONS:
        return jsonify({"error": "Invalid jurisdiction."}), 400

    if not isinstance(k, int) or k < 1:
        return jsonify({"error": "Invalid k."}), 400
    
    try:
        results = retrieve(query=query, jurisdiction=jurisdiction, k=k)
    except ValueError as e:
        return jsonify({"error": f"Invalid input: {e}"}), 400
    
    except RuntimeError as e:
        return jsonify({"error": f"Retrieval failed: {e}"}), 500

    return (
        jsonify(
            {
            "query": query,
            "jurisdiction": jurisdiction,
            "result_count": len(results),
            "results": results
            }
        ),
        200
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)