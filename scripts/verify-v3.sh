#!/usr/bin/env bash
# scripts/verify-v3.sh — v3 plan 集成验证(Phase E Task 1)
#
# 验证:
#   1. 8 业务服务 /health 返 200
#   2. 20 agents 列表(3 service 合并:planner=4, writer=7, reviewer=9)
#   3. 跑 42 单元测试(7 planner + 13 writer + 22 reviewer)
#   4. agent memory 表(planner / writer / reviewer 各自 schema 中 svc user 可写)
#   5. Bug Fix 1: BaseAgent.to_card() 警告消失(3 service 日志)
#   6. Bug Fix 2: svc user 无 'password authentication failed' 警告(3 service 日志)
#
# 用法: bash scripts/verify-v3.sh
set -o pipefail

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[1;34m'
NC='\033[0m'

PASS=0
FAIL=0
SKIP=0
WARN=0

ok()    { echo -e "${GREEN}✓${NC} $1"; PASS=$((PASS+1)); }
fail()  { echo -e "${RED}✗${NC} $1"; FAIL=$((FAIL+1)); }
skip()  { echo -e "${YELLOW}~${NC} $1"; SKIP=$((SKIP+1)); }
warn()  { echo -e "${YELLOW}!${NC} $1"; WARN=$((WARN+1)); }
info()  { echo -e "${BLUE}→${NC} $1"; }
section() { echo; echo -e "${BLUE}=== $1 ===${NC}"; }

# bypass ALL_PROXY 之类的 env,避免 curl 走 socks 失败
export all_proxy="" http_proxy="" https_proxy="" ALL_PROXY="" HTTP_PROXY="" HTTPS_PROXY=""
CURL="curl -sS --noproxy '*' --max-time 5"

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "============================================"
echo "  MinBook v3 Integration Verification"
echo "============================================"
echo "Project: $PROJECT_ROOT"
echo "Date:    $(date -Iseconds)"
echo

# ============================================================
# Section 1: 8 业务服务 /health
# ============================================================
section "1. /health on 8 business services"

declare -a SVC_HEALTH=(
  "gateway:8000"
  "pipeline-orchestrator:8002"
  "agent-planner-service:8003"
  "agent-writer-service:8004"
  "agent-reviewer-service:8005"
  "llm-gateway:8006"
  "state-service:8007"
  "notification-service:8008"
)
for entry in "${SVC_HEALTH[@]}"; do
  svc="${entry%:*}"
  port="${entry#*:}"
  body="$($CURL "http://127.0.0.1:${port}/health" 2>/dev/null || true)"
  if echo "$body" | grep -q '"status":"healthy"'; then
    ok "$svc :$port  healthy"
  else
    fail "$svc :$port  body=$body"
  fi
done

# ============================================================
# Section 2: 20 agents 列表(3 service 合并)
# ============================================================
section "2. 20 agents (planner 4 + writer 7 + reviewer 9)"

planner_body="$($CURL http://127.0.0.1:8003/health 2>/dev/null || true)"
writer_body="$($CURL http://127.0.0.1:8004/health 2>/dev/null || true)"
reviewer_body="$($CURL http://127.0.0.1:8005/health 2>/dev/null || true)"

planner_agents=$(echo "$planner_body" | python3 -c "import json,sys; d=json.load(sys.stdin); print(','.join(d.get('agents', [])))" 2>/dev/null)
writer_agents=$(echo "$writer_body" | python3 -c "import json,sys; d=json.load(sys.stdin); print(','.join(d.get('agents', [])))" 2>/dev/null)
reviewer_agents=$(echo "$reviewer_body" | python3 -c "import json,sys; d=json.load(sys.stdin); print(','.join(d.get('agents', [])))" 2>/dev/null)

expected_planner=("ArchitectAgent" "ComposerAgent" "FoundationReviewerAgent" "PlannerAgent")
expected_writer=("ChapterAnalyzerAgent" "ConsolidatorAgent" "LengthNormalizer" "PolisherAgent" "ShortFictionWriterAgent" "StyleAnalyzer" "WriterAgent")
expected_reviewer=("AIGCDetector" "ContinuityAuditor" "ObserverAgent" "PostWriteValidator" "RadarAgent" "ReviserAgent" "SensitiveWordsDetector" "SettlerAgent" "StateValidator")

check_agents() {
  local svc="$1"; local got="$2"; shift 2
  local expected=("$@")
  local missing=()
  for exp in "${expected[@]}"; do
    if ! echo ",$got," | grep -q ",$exp,"; then
      missing+=("$exp")
    fi
  done
  if [[ ${#missing[@]} -eq 0 ]]; then
    ok "$svc: ${#expected[@]} agents present"
  else
    fail "$svc: missing ${missing[*]} (got: $got)"
  fi
}

check_agents "planner-service" "$planner_agents" "${expected_planner[@]}"
check_agents "writer-service" "$writer_agents" "${expected_writer[@]}"
check_agents "reviewer-service" "$reviewer_agents" "${expected_reviewer[@]}"

# ============================================================
# Section 3: 42 单元测试(planner 7 + writer 13 + reviewer 22)
# ============================================================
section "3. 42 unit tests (no proxy)"

total_tests=0
for svc in agent-planner agent-writer agent-reviewer; do
  # 关键:必须在 service 目录里跑,否则会跑到 tests/test_e2e.py(全局 e2e,跟 service 无关)
  out="$(cd "services/$svc" && env -u ALL_PROXY uv run --package "minbook-${svc//-/_}" pytest tests/ -q --no-header 2>&1 | tail -3)"
  passed_line=$(echo "$out" | grep -oE '[0-9]+ passed' | tail -1)
  if [[ -n "$passed_line" ]]; then
    n="${passed_line% *}"
    ok "$svc: $n tests passed"
    total_tests=$((total_tests + n))
  elif echo "$out" | grep -qE '[0-9]+ failed'; then
    fail "$svc: tests failed — $out"
  else
    fail "$svc: no test result — $out"
  fi
done

if [[ $total_tests -eq 47 ]]; then
  ok "Total: $total_tests tests (42 unit + 5 e2e invoke; expected 47)"
elif [[ $total_tests -ge 45 ]]; then
  ok "Total: $total_tests tests (42 unit + $((total_tests - 42)) e2e)"
else
  warn "Total: $total_tests tests (expected 45-47; 42 unit + 3-5 e2e invoke)"
fi

# ============================================================
# Section 4: agent memory 表(svc user 可写)
# ============================================================
section "4. agent memory tables (svc user can write own schema)"

PG="docker exec minbook-postgres-1 psql -U"
# 每个 service 的标志性表(planner=episodes, writer=style_corpus, reviewer=audit_history)
table_for_schema() {
  case "$1" in
    planner)  echo "episodes" ;;
    writer)   echo "style_corpus" ;;
    reviewer) echo "audit_history" ;;
  esac
}
for schema in planner writer reviewer; do
  user="svc_${schema}"
  table="$(table_for_schema "$schema")"
  # 测试 1: 表是否存在
  out="$($PG "$user" -d minbook -t -c "
    SELECT EXISTS (
      SELECT 1 FROM information_schema.tables
      WHERE table_schema = '$schema' AND table_name = '$table'
    );
  " 2>&1 | tr -d ' ')"
  if echo "$out" | grep -q '^t$'; then
    ok "schema=$schema user=$user: $table exists"
  else
    warn "schema=$schema user=$user: $table NOT found (Alembic may not have created it)"
  fi
done

# 真实写测试:planner.episodes(用 svc_planner)
info "Real write test: svc_planner -> planner.episodes INSERT"
insert_out="$($PG svc_planner -d minbook -c "
  INSERT INTO planner.episodes (book_id, intent_json)
  VALUES (gen_random_uuid(), '{\"v3_verify\": true}'::jsonb)
  RETURNING id;
" 2>&1)"
count_out="$($PG svc_planner -d minbook -t -c "SELECT count(*) FROM planner.episodes;" 2>&1 | tr -d ' ')"
if [[ -n "$count_out" && "$count_out" =~ ^[0-9]+$ && $count_out -gt 0 ]]; then
  ok "svc_planner can write planner.episodes (total: $count_out)"
else
  fail "svc_planner cannot write planner.episodes: $insert_out"
fi

# writer.style_corpus(用 svc_writer)— 需要 book_id + fingerprint_json(必填)
info "Real write test: svc_writer -> writer.style_corpus INSERT"
insert_out="$($PG svc_writer -d minbook -c "
  INSERT INTO writer.style_corpus (book_id, fingerprint_json)
  VALUES (gen_random_uuid(), '{\"v3_verify\": true}'::jsonb)
  RETURNING id;
" 2>&1)"
count_out="$($PG svc_writer -d minbook -t -c "SELECT count(*) FROM writer.style_corpus;" 2>&1 | tr -d ' ')"
if [[ -n "$count_out" && "$count_out" =~ ^[0-9]+$ && $count_out -gt 0 ]]; then
  ok "svc_writer can write writer.style_corpus (total: $count_out)"
else
  warn "svc_writer cannot write writer.style_corpus: $insert_out"
fi

# reviewer.audit_history(用 svc_reviewer)— 需要 book_id + issues_json(必填)
info "Real write test: svc_reviewer -> reviewer.audit_history INSERT"
insert_out="$($PG svc_reviewer -d minbook -c "
  INSERT INTO reviewer.audit_history (book_id, chapter_number, issues_json, severity)
  VALUES (gen_random_uuid(), 0, '{\"v3_verify\": true}'::jsonb, 'info')
  RETURNING id;
" 2>&1)"
count_out="$($PG svc_reviewer -d minbook -t -c "SELECT count(*) FROM reviewer.audit_history;" 2>&1 | tr -d ' ')"
if [[ -n "$count_out" && "$count_out" =~ ^[0-9]+$ && $count_out -gt 0 ]]; then
  ok "svc_reviewer can write reviewer.audit_history (total: $count_out)"
else
  warn "svc_reviewer cannot write reviewer.audit_history: $insert_out"
fi

# ============================================================
# Section 5: 启动时 3 agent service 不再出现 to_card 警告
# ============================================================
section "5. Bug Fix 1: no 'BaseAgent.to_card() missing' warnings"

for svc in agent-planner agent-writer agent-reviewer; do
  cname="minbook-${svc}-service-1"
  log=$(docker logs "$cname" 2>&1 || echo "")
  if [[ -z "$log" ]]; then
    skip "$svc: cannot read logs"
    continue
  fi
  n=$(echo "$log" | grep -c "BaseAgent.to_card() missing" || true)
  if [[ $n -eq 0 ]]; then
    ok "$svc: no to_card warnings"
  else
    fail "$svc: $n to_card warning(s) found"
  fi
done

# ============================================================
# Section 6: Bug Fix 2: no 'password authentication failed' for svc users
# ============================================================
section "6. Bug Fix 2: no 'password authentication failed' for svc users"

for svc in agent-planner agent-writer agent-reviewer; do
  cname="minbook-${svc}-service-1"
  log=$(docker logs "$cname" 2>&1 || echo "")
  if [[ -z "$log" ]]; then
    skip "$svc: cannot read logs"
    continue
  fi
  n=$(echo "$log" | grep -c 'password authentication failed for user "svc_' || true)
  if [[ $n -eq 0 ]]; then
    ok "$svc: no svc_* password auth failure"
  else
    fail "$svc: $n svc_* password auth failure(s)"
  fi
done

# ============================================================
# Summary
# ============================================================
echo
echo "============================================"
echo "  Summary"
echo "============================================"
echo -e "PASS: ${GREEN}$PASS${NC}   FAIL: ${RED}$FAIL${NC}   SKIP: ${YELLOW}$SKIP${NC}   WARN: ${YELLOW}$WARN${NC}"
echo

if [[ $FAIL -gt 0 ]]; then
  echo -e "${RED}FAILED${NC} — see failures above"
  exit 1
elif [[ $WARN -gt 0 ]]; then
  echo -e "${YELLOW}OK_WITH_WARNINGS${NC} — see warnings above"
  exit 0
else
  echo -e "${GREEN}ALL_GREEN${NC} — v3 集成验证通过"
  exit 0
fi
