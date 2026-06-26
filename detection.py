import json
import os
import re
import statistics


GROQ_MODEL = "llama-3.3-70b-versatile"


def _local_ai_likelihood(text):
    lower = text.lower()
    ai_markers = [
        "it is important to note",
        "furthermore",
        "moreover",
        "in conclusion",
        "stakeholders",
        "paradigm shift",
        "transformative",
        "ethical implications",
        "responsible deployment",
        "plays a crucial role",
    ]
    human_markers = [
        "honestly",
        "ok so",
        "like",
        "kinda",
        "probably won't",
        "way too",
        "i was",
        "my friend",
    ]

    marker_score = min(0.35, sum(0.07 for marker in ai_markers if marker in lower))
    human_offset = min(0.25, sum(0.05 for marker in human_markers if marker in lower))
    length_bonus = 0.08 if len(text.split()) > 70 else 0.0
    score = 0.5 + marker_score + length_bonus - human_offset
    return max(0.05, min(0.95, score))


def _extract_json(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match:
            return json.loads(match.group(0))
    raise ValueError("Groq response did not contain valid JSON.")


def classify_with_groq(text):
    prompt = (
        "You are an AI provenance classifier for a creative writing platform. "
        "Return only valid JSON with keys: label, ai_score, reasoning. "
        "label must be one of likely_ai, likely_human, uncertain. "
        "ai_score must be a number from 0 to 1 where higher means more likely AI-generated. "
        "Avoid overclaiming because false positives against human writers are harmful.\n\n"
        f"Text:\n{text}"
    )

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        fallback_score = round(_local_ai_likelihood(text), 3)
        return {
            "label": "fallback_estimate",
            "ai_score": fallback_score,
            "reasoning": "GROQ_API_KEY was not configured, so a local fallback estimate was used for development evidence.",
            "status": "fallback",
            "model": GROQ_MODEL,
        }

    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "Return only compact JSON. Do not include markdown fences.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        content = completion.choices[0].message.content
        parsed = _extract_json(content)
        return {
            "label": str(parsed.get("label", "uncertain")),
            "ai_score": max(0.0, min(1.0, float(parsed.get("ai_score", 0.5)))),
            "reasoning": str(parsed.get("reasoning", "No reasoning returned."))[:500],
            "status": "ok",
            "model": GROQ_MODEL,
        }
    except Exception as exc:
        fallback_score = round(_local_ai_likelihood(text), 3)
        return {
            "label": "fallback_estimate",
            "ai_score": fallback_score,
            "reasoning": f"Groq request failed, so a local fallback estimate was used: {exc}",
            "status": "fallback",
            "model": GROQ_MODEL,
        }


def _sentences(text):
    parts = [part.strip() for part in re.split(r"[.!?]+", text) if part.strip()]
    return parts or [text.strip()]


def _words(text):
    return re.findall(r"[A-Za-z']+", text.lower())


def analyze_stylometrics(text):
    sentences = _sentences(text)
    words = _words(text)
    word_count = len(words)
    unique_words = len(set(words))
    sentence_lengths = [len(_words(sentence)) for sentence in sentences if sentence]
    avg_sentence_length = statistics.mean(sentence_lengths) if sentence_lengths else 0
    sentence_length_variance = statistics.pvariance(sentence_lengths) if len(sentence_lengths) > 1 else 0
    type_token_ratio = unique_words / word_count if word_count else 0
    punctuation_density = sum(1 for char in text if char in ",;:!?-()") / max(len(text), 1)

    repeated_words = 0
    for current, nxt in zip(words, words[1:]):
        if current == nxt:
            repeated_words += 1
    repetition_rate = repeated_words / max(word_count - 1, 1)

    variance_component = 0.25 if sentence_length_variance < 12 else 0.1 if sentence_length_variance < 35 else -0.05
    ttr_component = 0.2 if type_token_ratio < 0.48 else 0.08 if type_token_ratio < 0.62 else -0.08
    punctuation_component = 0.18 if punctuation_density < 0.018 else 0.08 if punctuation_density < 0.035 else -0.08
    avg_length_component = 0.12 if 16 <= avg_sentence_length <= 28 else 0.02
    repetition_component = min(0.17, repetition_rate * 8)
    short_text_component = 0.08 if word_count < 30 else 0.0

    ai_score = 0.42 + variance_component + ttr_component + punctuation_component + avg_length_component + repetition_component + short_text_component
    ai_score = round(max(0.0, min(1.0, ai_score)), 3)

    return {
        "ai_score": ai_score,
        "metrics": {
            "word_count": word_count,
            "sentence_count": len(sentences),
            "average_sentence_length": round(avg_sentence_length, 3),
            "sentence_length_variance": round(sentence_length_variance, 3),
            "type_token_ratio": round(type_token_ratio, 3),
            "punctuation_density": round(punctuation_density, 3),
            "repetition_rate": round(repetition_rate, 3),
        },
        "reasoning": "Stylometric score uses sentence uniformity, vocabulary diversity, punctuation density, average sentence length, and repetition.",
        "status": "ok",
    }
