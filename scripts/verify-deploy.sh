#!/usr/bin/env bash
# scripts/verify-deploy.sh — Phase 6 端到端冒烟测试
# 检查 8 个业务服务 /health + NATS + Grafana + PostgreSQL schemas + LLM 阈值。
# 用法: bash scripts/verify-deploy.sh  (或 make verify-deploy)

set -o pipefail

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PASS=0
FAIL=0
SKIP=0

ok()   { echo -e "${GREEN}✓${NC} $1"; PASS=$((PASS+1)); }
fail() { echo -e "${RED}✗${NC} $1"; FAIL=$((FAIL+1)); }
skip() { echo -e "${YELLOW}~${NC} $1"; SKIP=$((SKIP+1)); }
info() { echo -e "${BLUE}→${NC} $1"; }

# bypass ALL_PROXY 之类的 env,避免 curl 走 socks 失败
export all_proxy="" http_proxy="" https_proxy="" ALL_PROXY="" HTTP_PROXY="" HTTPS_PROXY=""
CURL="curl -sS --noproxy '*' --max-time 5"

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "============================================"
echo "  MinBook Deploy Verification (Phase 6)"
echo "============================================"
echo

# ---- 1. 8 业务服务 /health ----
info "Checking 8 service /health endpoints"
SVC_NAMES="gateway pipeline-orchestrator agent-planner-service agent-writer-service agent-reviewer-service llm-gateway state-service notification-service"
SVC_PORTS="8000 8002 8003 8004 8005 8006 8007 8008"
# 转成数组
set -- $SVC_NAMES
names=("$@")
set -- $SVC_PORTS
ports=("$@")
for i in 0 1 2 3 4 5 6 7; do
  svc="${names[$i]}"
  port="${ports[$i]}"
  body="$($CURL "http://127.0.0.1:${port}/health" 2>/dev/null || true)"
  if echo "$body" | grep -q '"status":"healthy"'; then
    ok "$svc (port $port): $body"
  else
    fail "$svc (port $port): no healthy response (got: $body)"
  fi
done
echo

# ---- 2. NATS ----
info "Checking NATS JetStream status"
nats_body="$($CURL http://127.0.0.1:8222/jsz 2>/dev/null || true)"
if echo "$nats_body" | grep -q '"server_id"'; then
  ok "NATS /jsz: server up"
else
  fail "NATS /jsz: no response"
fi
echo

# ---- 3. Grafana ----
info "Checking Grafana"
grafana_body="$($CURL http://127.0.0.1:3001/api/health 2>/dev/null || true)"
if echo "$grafana_body" | grep -q '"database"'; then
  ok "Grafana /api/health: $(echo "$grafana_body" | tr -d '\n')"
else
  fail "Grafana /api/health: no response (got: $grafana_body)"
fi
echo

# ---- 4. PostgreSQL schemas ----
info "Checking PostgreSQL schemas"
schemas="$(docker exec minbook-postgres-1 psql -U minbook -d minbook -tAc "SELECT schema_name FROM information_schema.schemata WHERE schema_name NOT IN ('pg_catalog','information_schema','pg_toast') ORDER BY schema_name;" 2>/dev/null || true)"
if [ -n "$schemas" ]; then
  schema_count=$(echo "$schemas" | wc -l | tr -d ' ')
  if [ "$schema_count" -ge 9 ]; then
    ok "PostgreSQL: $schema_count user schemas found"
    echo "$schemas" | sed 's/^/    /'
  else
    fail "PostgreSQL: only $schema_count schemas (expected >=9): $schemas"
  fi
else
  fail "PostgreSQL: cannot list schemas"
fi
echo

# ---- 5. 4 LLM 阈值存在(从 .env 读)----
info "Checking 4 LLM cost alert thresholds in .env"
if [ -f "$PROJECT_ROOT/.env" ]; then
  for key in LLM_COST_ALERT_DAILY_USD LLM_COST_ALERT_MONTHLY_USD LLM_COST_ALERT_PER_BOOK_USD LLM_COST_ALERT_SPIKE_MULTIPLIER; do
    if grep -q "^${key}=" "$PROJECT_ROOT/.env"; then
      val=$(grep "^${key}=" "$PROJECT_ROOT/.env" | head -1 | cut -d= -f2-)
      ok "$key = $val"
    else
      fail "$key missing from .env"
    fi
  done
else
  fail ".env not found at $PROJECT_ROOT/.env"
fi
echo

# ---- 6. Gateway auth token(可选;minimal app 不生成)----
info "Checking Gateway auth token (optional)"
if [ -f "$HOME/.minbook/auth.token" ]; then
  ok "Gateway auth token present: $(wc -c < "$HOME/.minbook/auth.token") bytes"
else
  skip "Gateway auth token not yet generated (minimal app, v2 plan will bootstrap)"
fi
echo

# ---- Summary ----
echo "============================================"
TOTAL=$((PASS+FAIL+SKIP))
echo -e "  ${GREEN}PASS${NC}: $PASS   ${RED}FAIL${NC}: $FAIL   ${YELLOW}SKIP${NC}: $SKIP   (total $TOTAL)"
echo "============================================"

if [ "$FAIL" -gt 0 ]; then
  echo -e "${RED}VERIFY FAILED${NC}"
  exit 1
fi
echo -e "${GREEN}VERIFY PASSED${NC}"
exit 0
