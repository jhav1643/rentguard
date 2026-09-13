
import os
from functools import wraps
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
 
import fitz  # PyMuPDF
import docx2txt
from dotenv import load_dotenv
from flask import Flask, jsonify, request
 
from services.agent_orchestrator.graph.build_graph import build_lease_analysis_graph
 
load_dotenv()
 
API_KEY = os.getenv("BACKEND_API_KEY")
app = Flask(__name__)
graph = build_lease_analysis_graph()  # compiled once at startup, reused per request
 
 
def require_api_key(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if API_KEY and request.headers.get("X-API-Key") != API_KEY:
            return jsonify({"error": "Invalid or missing API key."}), 401
        return f(*args, **kwargs)
    return wrapper
 
 
def extract_text_from_upload(file_storage) -> str:
    """Single-file text extraction -- deliberately separate from
    services.ingestion.loaders.loader, which is built for batch
    directory loading of known-format files, not one ad-hoc upload.
    """
    filename = file_storage.filename.lower()
 
    if filename.endswith(".pdf"):
        pdf_bytes = file_storage.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        return "\n".join(page.get_text() for page in doc)
 
    if filename.endswith(".docx"):
        return docx2txt.process(file_storage)
 
    raise ValueError(f"Unsupported file type: {filename}. Use PDF or DOCX.")
 
 
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200
 
 
@app.route("/analyze-lease", methods=["POST"])
@require_api_key
def analyze_lease():
    json_body = request.get_json(silent=True) or {}
    jurisdiction = request.form.get("jurisdiction") or json_body.get("jurisdiction")
    monthly_rent_bracket = request.form.get("monthly_rent_bracket") or json_body.get("monthly_rent_bracket")
 
    if not jurisdiction:
        return jsonify({"error": "'jurisdiction' is required."}), 400
 
    # Get lease text: either a fresh file upload, or echoed-back text
    # from the first call (see module docstring on the stateless flow)
    if "file" in request.files:
        try:
            lease_text = extract_text_from_upload(request.files["file"])
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
    else:
        lease_text = request.form.get("lease_text") or json_body.get("lease_text")
 
    if not lease_text or not lease_text.strip():
        return jsonify({"error": "No lease text provided (upload a file or pass lease_text)."}), 400
 
    input_state = {"lease_text": lease_text, "jurisdiction": jurisdiction}
    if monthly_rent_bracket:
        input_state["monthly_rent_bracket"] = monthly_rent_bracket
 
    try:
        result = graph.invoke(input_state)
    except Exception as e:
        return jsonify({"error": "Analysis failed.", "detail": str(e)}), 500
 
    if result.get("error"):
        return jsonify({"error": result["error"]}), 422
 
    if result.get("needs_user_input"):
        return jsonify({
            "needs_user_input": True,
            "prompt": result["user_input_prompt"],
            # echoed back so the client can resend on the next call
            "lease_text": lease_text,
            "jurisdiction": jurisdiction,
        }), 200
 
    return jsonify({
        "clause_risk_results": result.get("clause_risk_results", []),
        "explanations": result.get("explanations", []),
        "draft_communication": result.get("draft_communication"),
        "citation_check_passed": result.get("citation_check_passed"),
    }), 200
 
 
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
 