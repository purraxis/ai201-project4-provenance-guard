from uuid import uuid4

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv():
        return False

from flask import Flask, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from audit_log import append_appeal, append_submission, find_latest_submission, read_log
from detection import analyze_stylometrics, classify_with_groq
from labels import label_for_attribution
from scoring import combine_scores


load_dotenv()

app = Flask(__name__)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)


@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "service": "Provenance Guard",
        "status": "running",
        "endpoints": {
            "submit": {
                "method": "POST",
                "path": "/submit",
                "required_json": ["text", "creator_id"],
            },
            "appeal": {
                "method": "POST",
                "path": "/appeal",
                "required_json": ["content_id", "creator_reasoning"],
            },
            "log": {
                "method": "GET",
                "path": "/log",
            },
        },
    })


def validation_error(message, field, status_code=400):
    return jsonify({"error": message, "field": field}), status_code


@app.route("/submit", methods=["POST"])
@limiter.limit("10 per minute;100 per day")
def submit():
    payload = request.get_json(silent=True) or {}
    text = payload.get("text")
    creator_id = payload.get("creator_id")

    if not isinstance(text, str) or not text.strip():
        return validation_error("Missing or empty required field: text", "text")
    if not isinstance(creator_id, str) or not creator_id.strip():
        return validation_error("Missing or empty required field: creator_id", "creator_id")

    content_id = str(uuid4())
    groq_signal = classify_with_groq(text.strip())
    stylometric_signal = analyze_stylometrics(text.strip())
    combined = combine_scores(
        groq_signal.get("ai_score"),
        stylometric_signal.get("ai_score"),
        {"groq": groq_signal.get("status"), "stylometric": stylometric_signal.get("status")},
    )
    label = label_for_attribution(combined["attribution"])

    decision = {
        "content_id": content_id,
        "creator_id": creator_id.strip(),
        "attribution": combined["attribution"],
        "confidence": combined["confidence"],
        "label": label,
        "status": "classified",
        "groq_score": groq_signal.get("ai_score"),
        "stylometric_score": stylometric_signal.get("ai_score"),
        "stylometric_metrics": stylometric_signal.get("metrics"),
        "signals_used": {
            "groq": groq_signal,
            "stylometric": stylometric_signal,
        },
        "scoring_notes": combined.get("notes", []),
    }
    append_submission(decision)

    return jsonify({
        "content_id": content_id,
        "creator_id": decision["creator_id"],
        "attribution": decision["attribution"],
        "confidence": decision["confidence"],
        "label": decision["label"],
        "signals_used": decision["signals_used"],
        "status": decision["status"],
    })


@app.route("/appeal", methods=["POST"])
def appeal():
    payload = request.get_json(silent=True) or {}
    content_id = payload.get("content_id")
    creator_reasoning = payload.get("creator_reasoning")

    if not isinstance(content_id, str) or not content_id.strip():
        return validation_error("Missing or empty required field: content_id", "content_id")
    if not isinstance(creator_reasoning, str) or not creator_reasoning.strip():
        return validation_error("Missing or empty required field: creator_reasoning", "creator_reasoning")

    original = find_latest_submission(content_id.strip())
    if not original:
        return jsonify({
            "error": "No original submission found for content_id.",
            "content_id": content_id.strip(),
        }), 404

    appeal_entry = append_appeal(content_id.strip(), creator_reasoning.strip(), original)
    return jsonify({
        "message": "Appeal received and queued for human review.",
        "content_id": content_id.strip(),
        "creator_id": original.get("creator_id"),
        "status": "under_review",
        "appeal": {
            "creator_reasoning": creator_reasoning.strip(),
            "timestamp": appeal_entry.get("timestamp"),
        },
        "original_decision": appeal_entry.get("original_decision"),
    })


@app.route("/log", methods=["GET"])
def log():
    limit = request.args.get("limit", default=50, type=int)
    limit = max(1, min(limit, 200))
    return jsonify({"entries": read_log(limit=limit)})


if __name__ == "__main__":
    app.run(debug=True)
