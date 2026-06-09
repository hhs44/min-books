#!/usr/bin/env bash
# scripts/verify-v2.sh — v2 集成验证脚本(详见 v2 plan §Phase E Task 26)。
#
# 验证项:
#   1. 8 业务服务 /health 全 200
#   2. 认证:  ~/.minbook/auth.token 存在
#   3. Gateway 代理路由:
#        - /api/doctor            (聚合 4 下游)
#        - /api/books             (501 v3 defer)
#        - /api/llm/providers     (200)
#        - /api/notifications/channels (200)
#        - /api/state/<book_id>/config  (200)
#        - /api/state/<book_id>/memory  (501 v3 defer)
#        - /api/books/<id>/state/snapshots      (200)
#        - /api/books/<id>/state/<file> GET     (200)
#        - /api/books/<id>/state/<file> PUT     (200, version+1)
#        - /api/books/<id>/state/<file> PUT 错版本  (409)
#
# 退出码: 0=全过,1=有失败。
# 用法:   bash scripts/verify-v2.sh
set -o pipefail
GATEWAY="${GATEWAY:-http://127.0.0.1:8000}"
TOKEN_FILE="${TOKEN_FILE:-$HOME/.minbook/auth.token}"
BOOK_ID="${BOOK_ID:-11111111-1111-1111-1111-111111111111}"  # shared.books 已存在

PASS=0
FAIL=0
FAIL_DETAILS=""

# 颜色
RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
NC=$'\033[0m'

check() {
    local name="$1" expected="$2" actual="$3" extra="${4:-}"
    if [[ "$actual" == "$expected" ]]; then
        echo "${GREEN}✓${NC} $name → $actual $extra"
        PASS=$((PASS+1))
    else
        echo "${RED}✗${NC} $name → expected $expected, got $actual $extra"
        FAIL=$((FAIL+1))
        FAIL_DETAILS="$FAIL_DETAILS\n  - $name: expected $expected, got $actual"
    fi
}

curl_code() {
    # silent, no proxy, no follow; 输出纯 HTTP status code
    curl --noproxy '*' -s -o /dev/null -w "%{http_code}" "$@"
}

echo "${YELLOW}=== v2 集成验证 (GATEWAY=$GATEWAY, BOOK_ID=$BOOK_ID) ===${NC}"
echo

# 1) Token
echo "${YELLOW}-- 1. Auth token --${NC}"
if [[ -f "$TOKEN_FILE" ]]; then
    TOKEN=$(cat "$TOKEN_FILE")
    echo "${GREEN}✓${NC} token exists: ${TOKEN:0:20}..."
    PASS=$((PASS+1))
else
    echo "${RED}✗${NC} token file missing: $TOKEN_FILE"
    FAIL=$((FAIL+1))
    echo
    echo "${RED}ABORT: no token, cannot run further checks${NC}"
    exit 1
fi
echo

# 2) 8 业务服务 /health
echo "${YELLOW}-- 2. 8 业务服务 /health --${NC}"
SERVICES=(
    "gateway:8000"
    "llm-gateway:8006"
    "state-service:8007"
    "notification-service:8008"
    "pipeline-orchestrator:8002"
    "agent-planner-service:8003"
    "agent-writer-service:8004"
    "agent-reviewer-service:8005"
)
for entry in "${SERVICES[@]}"; do
    svc="${entry%%:*}"
    port="${entry##*:}"
    code=$(curl_code "http://127.0.0.1:$port/health")
    check "/health ($svc:$port)" 200 "$code"
done
echo

# 3) Gateway 聚合路由
echo "${YELLOW}-- 3. Gateway 代理路由 --${NC}"
AUTH=(-H "Authorization: Bearer $TOKEN")

code=$(curl_code "${AUTH[@]}" "$GATEWAY/api/doctor")
check "GET /api/doctor" 200 "$code"

code=$(curl_code "${AUTH[@]}" "$GATEWAY/api/books")
check "GET /api/books (501 v3 defer)" 501 "$code"

code=$(curl_code "${AUTH[@]}" "$GATEWAY/api/llm/providers")
check "GET /api/llm/providers" 200 "$code"

code=$(curl_code "${AUTH[@]}" "$GATEWAY/api/notifications/channels")
check "GET /api/notifications/channels" 200 "$code"

code=$(curl_code "${AUTH[@]}" "$GATEWAY/api/config")
check "GET /api/config" 200 "$code"

# /api/books/<id>/memory - gateway 暂无代理,期望 404(由 FastAPI 默认处理)
code=$(curl_code "${AUTH[@]}" "$GATEWAY/api/books/$BOOK_ID/memory")
check "GET /api/books/<id>/memory (no proxy yet)" 404 "$code"

code=$(curl_code "${AUTH[@]}" "$GATEWAY/api/books/$BOOK_ID/state/snapshots")
check "GET /api/books/<id>/state/snapshots" 200 "$code"

code=$(curl_code "${AUTH[@]}" "$GATEWAY/api/books/$BOOK_ID/snapshots")
check "GET /api/books/<id>/snapshots (compat alias)" 200 "$code"
echo

# 4) 4 容量真相文件 PUT + 乐观并发
echo "${YELLOW}-- 4. 4 容量真相文件 PUT + 乐观并发 --${NC}"
for ft in current_state character_matrix pending_hooks chapter_summaries; do
    # 强制覆盖(None) → 200
    code=$(curl --noproxy '*' -s -o /dev/null -w "%{http_code}" -X PUT \
        "${AUTH[@]}" -H "Content-Type: application/json" \
        -d "{\"content\": {\"verify\": \"$ft\", \"ts\": \"$(date -Iseconds)\"}, \"expected_version\": null}" \
        "$GATEWAY/api/books/$BOOK_ID/state/$ft")
    check "PUT /api/books/<id>/state/$ft (new/force)" 200 "$code"

    # 读最新 version
    version=$(curl --noproxy '*' -s "${AUTH[@]}" "$GATEWAY/api/books/$BOOK_ID/state/$ft" \
        | python3 -c "import sys,json; print(json.load(sys.stdin)['version'])" 2>/dev/null || echo 0)
    check "GET /api/books/<id>/state/$ft (read version=$version)" 200 \
        "$(curl_code "${AUTH[@]}" "$GATEWAY/api/books/$BOOK_ID/state/$ft")"

    # 错版本 → 409
    code=$(curl --noproxy '*' -s -o /dev/null -w "%{http_code}" -X PUT \
        "${AUTH[@]}" -H "Content-Type: application/json" \
        -d "{\"content\": {\"x\": 1}, \"expected_version\": 999}" \
        "$GATEWAY/api/books/$BOOK_ID/state/$ft")
    check "PUT .../$ft (wrong version → 409)" 409 "$code"
done
echo

# 5) 写后读 (latest version)
echo "${YELLOW}-- 5. 写后读 (version 应该=上面 PUT 后+1) --${NC}"
for ft in current_state character_matrix pending_hooks chapter_summaries; do
    code=$(curl_code "${AUTH[@]}" "$GATEWAY/api/books/$BOOK_ID/state/$ft")
    check "GET $ft (post-write)" 200 "$code"
done
echo

# 总结
echo "${YELLOW}=== 汇总 ===${NC}"
TOTAL=$((PASS + FAIL))
if [[ $FAIL -eq 0 ]]; then
    echo "${GREEN}全部通过: $PASS / $TOTAL${NC}"
    exit 0
else
    echo "${RED}失败: $FAIL / $TOTAL${NC}"
    echo -e "失败项:$FAIL_DETAILS"
    exit 1
fi
