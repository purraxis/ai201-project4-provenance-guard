LIKELY_HUMAN_MAX = 0.35
LIKELY_AI_MIN = 0.75
GROQ_WEIGHT = 0.65
STYLOMETRIC_WEIGHT = 0.35


def clamp_score(value):
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.5
    return max(0.0, min(1.0, numeric))


def attribution_for_score(score):
    score = clamp_score(score)
    if score <= LIKELY_HUMAN_MAX:
        return "likely_human"
    if score >= LIKELY_AI_MIN:
        return "likely_ai"
    return "uncertain"


def combine_scores(groq_score, stylometric_score, signal_statuses=None):
    groq = clamp_score(groq_score)
    stylometric = clamp_score(stylometric_score)
    signal_statuses = signal_statuses or {}

    weighted = (GROQ_WEIGHT * groq) + (STYLOMETRIC_WEIGHT * stylometric)
    notes = []

    if abs(groq - stylometric) >= 0.45:
        weighted = 0.5 + ((weighted - 0.5) * 0.55)
        notes.append("Signals strongly disagreed, so the score was nudged toward uncertainty.")

    if signal_statuses.get("groq") == "fallback":
        notes.append("Groq fallback was used, so the audit log marks the LLM signal as development evidence.")

    confidence = round(clamp_score(weighted), 3)
    return {
        "confidence": confidence,
        "attribution": attribution_for_score(confidence),
        "weights": {
            "groq": GROQ_WEIGHT,
            "stylometric": STYLOMETRIC_WEIGHT,
        },
        "notes": notes,
    }
