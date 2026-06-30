# Provenance Guard

Provenance Guard is a Flask backend for a creative writing platform. It accepts text submissions, estimates whether a piece is likely AI-generated, likely human-written, or uncertain, returns a confidence score, generates a transparency label, supports creator appeals, applies rate limiting, and writes structured audit logs.

The project is designed around CodePath AI201 Project 4 grading evidence: implementation, `planning.md`, curl outputs, rate-limit evidence, audit-log samples, AI usage notes, and final audit are all visible in the repo.

## Architecture Overview

Submission path:

```text
POST /submit
  -> input validation
  -> unique content_id
  -> Groq LLM signal
  -> stylometric signal
  -> confidence scoring
  -> transparency label
  -> structured audit log
  -> JSON response
```

Appeal path:

```text
POST /appeal
  -> find original content_id
  -> update status to under_review
  -> log appeal with original decision
  -> JSON confirmation
```

The full Mermaid diagram and design narrative are in `planning.md`.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set:

```bash
GROQ_API_KEY=your_key_here
```

Never commit `.env`. It is ignored in `.gitignore`. If `GROQ_API_KEY` is missing, the app uses a local development fallback and marks the Groq signal as `fallback` in the response and audit log.

Run the app:

```bash
flask --app app run
```

## API Endpoints

### POST `/submit`

Request:

```bash
curl -s -X POST http://127.0.0.1:5000/submit \
  -H "Content-Type: application/json" \
  -d '{"creator_id":"creator-ai","text":"It is important to note that artificial intelligence represents a transformative paradigm shift..."}'
```

Response includes:

- `content_id`
- `creator_id`
- `attribution`
- `confidence`
- `label`
- `signals_used`
- `status`

Example from `sample_outputs/clearly_ai.json` generated with live Groq:

```json
{
  "attribution": "likely_ai",
  "confidence": 0.796,
  "label": "Transparency notice: This submission appears likely to be AI-generated. The system is confident, but this is not a final judgment and the creator may appeal.",
  "status": "classified"
}
```

Validation examples are saved in `sample_outputs/validation_missing_text.json`, `sample_outputs/validation_missing_creator_id.json`, and `sample_outputs/validation_errors.json`.

### POST `/appeal`

Request:

```bash
curl -s -X POST http://127.0.0.1:5000/appeal \
  -H "Content-Type: application/json" \
  -d '{"content_id":"PASTE-CONTENT-ID","creator_reasoning":"I wrote this from my own notes."}'
```

Valid appeal response from `sample_outputs/appeal_valid.json`:

```json
{
  "message": "Appeal received and queued for human review.",
  "status": "under_review",
  "original_decision": {
    "attribution": "likely_human",
    "confidence": 0.321
  }
}
```

Invalid appeal response from `sample_outputs/appeal_invalid.json`:

```json
{
  "content_id": "not-a-real-id",
  "error": "No original submission found for content_id."
}
```

### GET `/log`

```bash
curl -s http://127.0.0.1:5000/log?limit=20
```

Returns recent structured audit entries:

```json
{
  "entries": [
    {
      "event_type": "submission",
      "content_id": "89962535-7f12-46f0-91ff-a7a9dfdee1fa",
      "creator_id": "creator-ai",
      "attribution": "likely_ai",
      "confidence": 0.796,
      "groq_score": 0.8,
      "stylometric_score": 0.79,
      "status": "classified"
    },
    {
      "event_type": "submission",
      "content_id": "38803496-c9ea-47f2-93c1-79b6e39b8225",
      "creator_id": "creator-human",
      "attribution": "likely_human",
      "confidence": 0.321,
      "groq_score": 0.23,
      "stylometric_score": 0.49,
      "status": "classified"
    },
    {
      "event_type": "appeal",
      "content_id": "38803496-c9ea-47f2-93c1-79b6e39b8225",
      "status": "under_review",
      "creator_reasoning": "I wrote this from my own restaurant visit notes, including personal details from that day."
    }
  ]
}
```

Full captured output is saved in `sample_outputs/log_sample.json`.

## Detection Signals

### Signal 1: Groq LLM Classification

The Groq signal uses `llama-3.3-70b-versatile` and asks for structured JSON with `label`, `ai_score`, and `reasoning`. It measures holistic semantic and stylistic patterns such as generic framing, polished transitions, and formulaic explanation.

Why I chose it: an LLM can notice semantic and rhetorical cues that pure statistics miss.

What it misses: it can be overconfident, may misclassify formal human writing, and depends on API availability. If the API fails or no key is configured, the app records a fallback status.

### Signal 2: Stylometric Heuristics

The stylometric signal is pure Python. It measures:

- sentence length variance
- type-token ratio
- punctuation density
- average sentence length
- repetition rate

Why I chose it: these metrics are transparent and structurally different from an LLM judgment.

What it misses: repetitive poetry, formal academic prose, non-native English, and heavily edited AI text can all confuse style-based metrics.

The two signals are distinct because one is semantic/model-based and the other is structural/statistical.

## Confidence Scoring

Higher confidence means more likely AI-generated.

Formula:

```text
combined = 0.65 * groq_ai_score + 0.35 * stylometric_ai_score
```

Thresholds:

| Score Range | Attribution |
|---|---|
| `0.00` to `0.35` | `likely_human` |
| `0.36` to `0.74` | `uncertain` |
| `0.75` to `1.00` | `likely_ai` |

If the two signals strongly disagree, the score is nudged toward `0.5`. This uncertainty band matters because a false positive against a human creator is worse than letting a questionable submission remain uncertain.

Example score spread from saved outputs:

| Input Type | Groq Score | Stylometric Score | Combined Confidence | Attribution | Label Variant |
|---|---:|---:|---:|---|---|
| Clearly AI-generated | 0.80 | 0.79 | 0.796 | `likely_ai` | High-confidence AI |
| Clearly human casual | 0.23 | 0.49 | 0.321 | `likely_human` | High-confidence human |
| Borderline formal human | 0.23 | 0.74 | 0.450 | `uncertain` | Uncertain |
| Borderline lightly edited AI | 0.23 | 0.64 | 0.373 | `uncertain` | Uncertain |

## Transparency Labels

| Variant | Exact Text |
|---|---|
| High-confidence AI | "Transparency notice: This submission appears likely to be AI-generated. The system is confident, but this is not a final judgment and the creator may appeal." |
| High-confidence human | "Transparency notice: This submission appears likely to be human-written. The system found limited signs of AI generation, but no detector is perfect." |
| Uncertain | "Transparency notice: This submission has mixed signals, so we are not labeling it as clearly AI-generated or clearly human-written. A creator appeal is available if needed." |

These strings are defined in `labels.py`, written in `planning.md`, and returned by the API.

## Appeals Workflow

A creator can contest a decision by submitting `content_id` and `creator_reasoning` to `POST /appeal`. The system finds the original decision, changes the status to `under_review`, logs the appeal reasoning alongside the original attribution and signal scores, and returns a confirmation.

A human reviewer would see:

- content ID
- creator ID
- original attribution
- combined confidence
- Groq score and reasoning
- stylometric score and metrics
- transparency label
- creator appeal reasoning

## Rate Limiting

`POST /submit` uses Flask-Limiter:

```python
@limiter.limit("10 per minute;100 per day")
```

The limiter is configured with `storage_uri="memory://"` for local development.

Reasoning: a real creator may submit several drafts in a session, so 10 per minute is generous for human use. A script trying to flood the API or burn Groq quota will exceed that quickly. The 100 per day cap gives a reasonable daily ceiling for one creator or IP.

Rate-limit evidence from `sample_outputs/rate_limit.txt`:

```text
200
200
200
200
200
200
200
200
200
200
429
429
```

Command:

```bash
./test_requests.sh rate-limit
```

## Audit Log

The runtime audit log is JSONL in `audit_log.jsonl`. It is ignored as a local runtime file, while grader-ready captured evidence is saved under `sample_outputs/`.

Submission entries include:

- `timestamp`
- `event_type`
- `content_id`
- `creator_id`
- `attribution`
- `confidence`
- `label`
- `groq_score`
- `stylometric_score`
- `stylometric_metrics`
- `status`

Appeal entries include:

- `timestamp`
- `event_type: appeal`
- `content_id`
- `creator_id`
- `creator_reasoning`
- `status: under_review`
- `original_decision`

See `sample_outputs/log_sample.json` for at least 3 visible entries including one appeal.

## Known Limitations

Formal human academic writing may be misclassified as more AI-like because it can have low punctuation density, polished structure, and balanced sentence length. This affects both the LLM signal and the stylometric signal.

Simple repetitive poetry may trigger stylometric false positives because repetition and short sentence patterns look formulaic. Non-native English writing may also be misread because unusual phrasing can be interpreted as detector artifacts. Heavily edited AI text may look human because editing can add irregularity and personal detail.

## Spec Reflection

One way the spec helped: writing thresholds and exact label strings in `planning.md` before coding made it straightforward to keep `scoring.py`, `labels.py`, and README evidence aligned.

One implementation divergence: the original plan said Groq failures would use a neutral fallback score. During testing, that made all sample outputs uncertain and weakened the grading evidence. I revised the fallback to a local development estimate that is clearly marked as `fallback` while preserving the uncertainty behavior when signals disagree.

## AI Usage

1. I asked Codex to convert the CodePath PDF and project prompt into a rubric checklist and implementation plan. It produced the checklist, file plan, scoring defaults, and evidence requirements. I revised the workflow to require `planning.md` before implementation and to make `README.md` the canonical grading artifact so that every required feature had visible evidence.

2. I asked Codex to implement the backend from the approved plan. It produced the Flask routes, Groq detection function, stylometric heuristic function, scoring logic, label mapping, audit logging, tests, sample outputs, and README evidence. I reviewed the implementation, ran the unit tests and API tests, and corrected the fallback/scoring behavior because the first version made too many saved examples uncertain.

3. I used Codex to help audit the final project against the rubric. I then manually verified the live API behavior with curl commands, checked that Groq was returning `status: ok`, confirmed that `/submit`, `/appeal`, `/log`, rate limiting, and sample outputs worked, and updated README values so the documentation matched the actual saved evidence.

## Walkthrough/Demo

Video walkthrough: [Canva demo video](https://canva.link/p6c19mp12q4wmae)

The walkthrough should show:

- starting the Flask app
- submitting clearly AI-generated and clearly human-written examples
- showing different confidence scores and labels
- submitting an appeal
- viewing `/log`
- running the rate-limit command and showing `429`

## Test Evidence

Run unit tests:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Run API evidence generation while the server is running:

```bash
./test_requests.sh samples
./test_requests.sh rate-limit
```

Files generated or saved:

- `sample_outputs/clearly_ai.json`
- `sample_outputs/human_casual.json`
- `sample_outputs/formal_human_borderline.json`
- `sample_outputs/lightly_edited_ai_borderline.json`
- `sample_outputs/short_text.json`
- `sample_outputs/validation_missing_text.json`
- `sample_outputs/validation_missing_creator_id.json`
- `sample_outputs/validation_errors.json`
- `sample_outputs/appeal_valid.json`
- `sample_outputs/appeal_invalid.json`
- `sample_outputs/log_sample.json`
- `sample_outputs/rate_limit.txt`

## Final Audit

Estimated score: 25/29 required points, with no stretch points claimed yet.

Required features completed:

- `planning.md` with Architecture and AI Tool Plan sections
- Flask `POST /submit`
- Groq LLM signal function using `llama-3.3-70b-versatile`
- Groq structured JSON prompt
- graceful Groq fallback
- pure Python stylometric signal with multiple metrics
- confidence scoring and uncertainty thresholds
- exact transparency labels
- `POST /appeal`
- `GET /log`
- structured audit logging
- Flask-Limiter with `10 per minute;100 per day`
- 429 evidence
- README evidence sections

Stretch features completed: none.

Missing or weak rubric areas:

- No stretch feature implemented.
- No API key is committed. The saved sample outputs in `sample_outputs/` were regenerated with live Groq using a transient environment variable.

Exact files changed:

- `README.md`
- `planning.md`
- `requirements.txt`
- `.gitignore`
- `.env.example`
- `app.py`
- `detection.py`
- `scoring.py`
- `labels.py`
- `audit_log.py`
- `test_requests.sh`
- `tests/test_core.py`
- `sample_outputs/*`

Commands/tests run:

```bash
python3 -m unittest discover -s tests -v
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/flask --app app run --host 127.0.0.1 --port 5000
./test_requests.sh samples
./test_requests.sh rate-limit
rg "## Architecture|## AI Tool Plan|Transparency notice|storage_uri=\"memory://\"|10 per minute" -n planning.md app.py labels.py
```

API outputs verified:

- `/submit` valid examples return `content_id`, attribution, confidence, label, signals, and status.
- `/submit` validation errors return `400`.
- `/appeal` valid content returns `under_review`.
- `/appeal` invalid content returns `404`.
- `/log` returns structured entries.
- rapid `/submit` calls return `429` after the limit is exceeded.

README evidence completed: yes.

`planning.md` evidence completed: yes.

Final submission checklist:

- Add real `GROQ_API_KEY` to local `.env` only when running locally.
- Re-run sample commands if fresh live Groq evidence is desired.
- Paste walkthrough video link into README.
- Submit GitHub repo link and walkthrough link in the Course Portal.
