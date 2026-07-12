#!/usr/bin/env bash
# SparkBench — unified LLM recipe benchmark for OpenAI-compatible endpoints.
# Benchmarks whatever is serving, produces a per-category scorecard + grade.
#
#   ./sparkbench.sh <recipe-label> [base-url]
#
# Default base-url: http://localhost:8000/v1  (model name defaults to "local-ai"
# or auto-detected by tool-eval-bench). Results: ~/bench/sparkbench/<label>_<timestamp>/
set -u
LABEL=${1:?usage: sparkbench.sh <recipe-label> [base-url]}
BASE=${2:-http://localhost:8000/v1}
MODEL=${SPARKBENCH_MODEL:-local-ai}
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PY=$ROOT/venv/bin/python
[ -x "$PY" ] || PY=$(command -v python3)
TS=$(date +%Y%m%d-%H%M%S)
OUT=$HOME/bench/sparkbench/${LABEL}_$TS
mkdir -p "$OUT"
exec > >(tee -a "$OUT/sparkbench.log") 2>&1
echo "SparkBench — $LABEL — $TS — $BASE"
echo "python: $PY"

# 0 readiness (waits up to 30 min for model load/compile)
for i in $(seq 1 120); do
  curl -sf -m 5 "$BASE/models" >/dev/null 2>&1 && \
  curl -sf -m 180 "$BASE/chat/completions" -H 'Content-Type: application/json' \
    -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}],\"max_tokens\":5}" >/dev/null 2>&1 && break
  sleep 15
done
echo "[0/6] server ready $(date)"

# system stability snapshot (before)
CID=$(docker ps --filter publish=8000 -q | head -1)
RST0=$(docker inspect "$CID" --format '{{.RestartCount}}' 2>/dev/null || echo 0)
OOM0=$(sudo dmesg 2>/dev/null | grep -c -E "NV_ERR_NO_MEMORY|oom-kill|Out of memory" || echo 0)

echo "[1/6] TOOLS + SPEED: tool-eval-bench full-63 + perf"
TEB=$(command -v tool-eval-bench || echo "$HOME/.local/bin/tool-eval-bench")
"$TEB" --base-url "$BASE" --model "$MODEL" --perf > "$OUT/tool-eval.rich.txt" 2>&1
grep -E "^Score:" "$OUT/tool-eval.rich.txt" || echo "WARN: no tool-eval score line"

echo "[2/6] AGENT: interpreter build $(date)"
$PY "$ROOT/agent_build_r2.py" "$LABEL" "$OUT/work_agent" "$ROOT/test_interp.py" "$OUT/round2"

echo "[3/6] REASON-logic $(date)"
$PY "$ROOT/logic_eval.py" "$LABEL" "$ROOT/logic_suite.json" "$OUT/round2"
cp "$ROOT/test_interp.py" "$OUT/round2/" 2>/dev/null
$PY "$ROOT/judge.py" "$OUT/round2" > "$OUT/round2/judge.out" 2>&1 || echo "WARN judge r2"

echo "[4/6] REASON-math + CONTEXT $(date)"
$PY "$ROOT/qa_eval.py" "$LABEL" "$ROOT/math_suite.json" "$OUT/round3" math_answers.json
$PY "$ROOT/qa_eval.py" "$LABEL" "$ROOT/longctx_suite.json" "$OUT/round3" longctx_answers.json "$ROOT/longctx_doc.txt"

echo "[5/6] LOAD + thinking forensics $(date)"
$PY "$ROOT/conc_eval.py" "$LABEL" "$OUT/round3"
$PY "$ROOT/think_probe.py" "$LABEL" "$OUT/round3"
$PY "$ROOT/judge3.py" "$OUT/round3" > "$OUT/round3/judge3.out" 2>&1 || echo "WARN judge r3"

# system stability snapshot (after) -> stability_sys.json
RST1=$(docker inspect "$CID" --format '{{.RestartCount}}' 2>/dev/null || echo 0)
OOM1=$(sudo dmesg 2>/dev/null | grep -c -E "NV_ERR_NO_MEMORY|oom-kill|Out of memory" || echo 0)
UPOK=false
curl -sf -m 10 "$BASE/models" >/dev/null 2>&1 && UPOK=true
$PY - <<PY
import json
json.dump({"container_restarts": max(0, $RST1 - $RST0),
           "oom_events": max(0, $OOM1 - $OOM0),
           "server_up_after": "$UPOK" == "true"}, open("$OUT/stability_sys.json", "w"), indent=2)
PY

echo "[6/6] SCORECARD $(date)"
$PY "$ROOT/sparkbench_report.py" --label "$LABEL" --tooleval "$OUT/tool-eval.rich.txt" \
  --round2 "$OUT/round2" --round3 "$OUT/round3" --out "$OUT"

$PY "$ROOT/sparkbench_leaderboard.py" "$HOME/bench/sparkbench" > /dev/null 2>&1 || true
echo "SPARKBENCH DONE $(date) -> $OUT/scorecard.md"
echo "leaderboard updated -> $HOME/bench/sparkbench/LEADERBOARD.md"
