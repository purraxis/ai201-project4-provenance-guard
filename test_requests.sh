#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:5000}"
OUT_DIR="${OUT_DIR:-sample_outputs}"
mkdir -p "$OUT_DIR"

post_json() {
  local endpoint="$1"
  local payload="$2"
  curl -s -X POST "$BASE_URL$endpoint" \
    -H "Content-Type: application/json" \
    -d "$payload"
}

samples() {
  post_json "/submit" '{"creator_id":"creator-ai","text":"It is important to note that artificial intelligence represents a transformative paradigm shift in modern creative ecosystems. Furthermore, artificial intelligence can optimize workflows, enhance productivity, and unlock scalable innovation across industries. Moreover, stakeholders must collaborate to ensure responsible deployment, ethical governance, and sustainable adoption. In conclusion, the benefits of artificial intelligence are numerous, but careful oversight remains essential for long-term success."}' > "$OUT_DIR/clearly_ai.json"

  post_json "/submit" '{"creator_id":"creator-human","text":"ok so i finally tried that new ramen place downtown and honestly? underwhelming. the broth was fine but they put WAY too much sodium in it and i was thirsty for like three hours after. my friend got the spicy version and said it was better. probably won'\''t go back unless someone drags me there"}' > "$OUT_DIR/human_casual.json"

  post_json "/submit" '{"creator_id":"creator-formal","text":"The relationship between monetary policy and asset price inflation has been extensively studied in the literature. Central banks face a fundamental tension between their mandate for price stability and the unintended consequences of prolonged low interest rates on equity and real estate valuations."}' > "$OUT_DIR/formal_human_borderline.json"

  post_json "/submit" '{"creator_id":"creator-borderline","text":"I'\''ve been thinking a lot about remote work lately. There are genuine tradeoffs: flexibility and no commute on one side, isolation and blurred work-life boundaries on the other. Studies show productivity varies widely by individual and role, so I do not think one policy fits everyone."}' > "$OUT_DIR/lightly_edited_ai_borderline.json"

  post_json "/submit" '{"creator_id":"missing-text"}' > "$OUT_DIR/validation_missing_text.json"
  post_json "/submit" '{"text":"This is missing a creator id."}' > "$OUT_DIR/validation_missing_creator_id.json"
  post_json "/submit" '{"creator_id":"short-text","text":"Tiny draft."}' > "$OUT_DIR/short_text.json"

  local content_id
  content_id="$(python3 -c 'import json; print(json.load(open("sample_outputs/human_casual.json"))["content_id"])')"
  post_json "/appeal" "{\"content_id\":\"$content_id\",\"creator_reasoning\":\"I wrote this from my own restaurant visit notes, including personal details from that day.\"}" > "$OUT_DIR/appeal_valid.json"
  post_json "/appeal" '{"content_id":"not-a-real-id","creator_reasoning":"This should fail because the content id is unknown."}' > "$OUT_DIR/appeal_invalid.json"
  curl -s "$BASE_URL/log?limit=20" > "$OUT_DIR/log_sample.json"
}

rate_limit() {
  : > "$OUT_DIR/rate_limit.txt"
  for i in $(seq 1 12); do
    curl -s -o /dev/null -w "%{http_code}\n" -X POST "$BASE_URL/submit" \
      -H "Content-Type: application/json" \
      -d '{"creator_id":"rate-limit-user","text":"This is a test submission for rate limit testing purposes only. It is long enough to pass validation and can be repeated quickly."}' \
      >> "$OUT_DIR/rate_limit.txt"
  done
}

case "${1:-samples}" in
  samples)
    samples
    ;;
  rate-limit)
    rate_limit
    ;;
  all)
    samples
    rate_limit
    ;;
  *)
    echo "Usage: $0 [samples|rate-limit|all]" >&2
    exit 1
    ;;
esac
