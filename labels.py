HIGH_CONFIDENCE_AI_LABEL = (
    "Transparency notice: This submission appears likely to be AI-generated. "
    "The system is confident, but this is not a final judgment and the creator may appeal."
)

HIGH_CONFIDENCE_HUMAN_LABEL = (
    "Transparency notice: This submission appears likely to be human-written. "
    "The system found limited signs of AI generation, but no detector is perfect."
)

UNCERTAIN_LABEL = (
    "Transparency notice: This submission has mixed signals, so we are not labeling it as clearly "
    "AI-generated or clearly human-written. A creator appeal is available if needed."
)


def label_for_attribution(attribution):
    labels = {
        "likely_ai": HIGH_CONFIDENCE_AI_LABEL,
        "likely_human": HIGH_CONFIDENCE_HUMAN_LABEL,
        "uncertain": UNCERTAIN_LABEL,
    }
    return labels.get(attribution, UNCERTAIN_LABEL)
