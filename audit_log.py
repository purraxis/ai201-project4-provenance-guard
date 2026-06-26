import json
from datetime import datetime, timezone
from pathlib import Path


AUDIT_LOG_PATH = Path("audit_log.jsonl")


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def append_log(entry, path=AUDIT_LOG_PATH):
    path = Path(path)
    record = {"timestamp": utc_now(), **entry}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def read_log(limit=50, path=AUDIT_LOG_PATH):
    path = Path(path)
    if not path.exists():
        return []
    entries = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries[-limit:]


def find_latest_submission(content_id, path=AUDIT_LOG_PATH):
    for entry in reversed(read_log(limit=1000, path=path)):
        if entry.get("event_type") == "submission" and entry.get("content_id") == content_id:
            return entry
    return None


def append_submission(decision, path=AUDIT_LOG_PATH):
    return append_log({"event_type": "submission", **decision}, path=path)


def append_appeal(content_id, creator_reasoning, original_decision, path=AUDIT_LOG_PATH):
    entry = {
        "event_type": "appeal",
        "content_id": content_id,
        "creator_id": original_decision.get("creator_id"),
        "creator_reasoning": creator_reasoning,
        "status": "under_review",
        "original_decision": {
            "attribution": original_decision.get("attribution"),
            "confidence": original_decision.get("confidence"),
            "label": original_decision.get("label"),
            "groq_score": original_decision.get("groq_score"),
            "stylometric_score": original_decision.get("stylometric_score"),
            "stylometric_metrics": original_decision.get("stylometric_metrics"),
        },
    }
    return append_log(entry, path=path)
