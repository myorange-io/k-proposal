#!/bin/bash
set -e

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${BLUE}[info]${NC} $1"; }
ok()    { echo -e "${GREEN}[ok]${NC} $1"; }
warn()  { echo -e "${YELLOW}[warn]${NC} $1"; }
fail()  { echo -e "${RED}[error]${NC} $1"; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "=========================================="
echo "  k-proposal 설치"
echo "=========================================="
echo ""

# ─── 1. Python 의존성 ───

info "Python 의존성 설치 중..."
if command -v pip3 &>/dev/null; then
    PIP=pip3
elif command -v pip &>/dev/null; then
    PIP=pip
else
    fail "pip를 찾을 수 없습니다. Python 설치를 확인하세요."
    exit 1
fi

$PIP install lxml python-docx matplotlib Pillow 2>/dev/null && ok "Python 의존성 설치 완료" || {
    warn "일부 패키지 설치 실패. 수동 설치: pip install lxml python-docx matplotlib Pillow"
}

# ─── 2. Node.js / kordoc 확인 및 설치 ───

KORDOC_AVAILABLE=false

if command -v npx &>/dev/null; then
    info "kordoc + pdfjs-dist 설치 중..."
    npm install -g kordoc pdfjs-dist 2>/dev/null || npm install -g kordoc 2>/dev/null || true
    if npx kordoc --version &>/dev/null 2>&1; then
        ok "kordoc $(npx kordoc --version 2>/dev/null) 사용 가능"
        KORDOC_AVAILABLE=true
    else
        warn "kordoc 설치 실패. HWP 파싱은 수동 HWPX 변환으로 대체됩니다."
    fi

    # @rhwp/core (HWPX/HWP WASM 검증용)
    if [ -f "$SCRIPT_DIR/package.json" ]; then
        info "@rhwp/core 설치 중 (HWPX 빌드 검증용)..."
        (cd "$SCRIPT_DIR" && npm install 2>/dev/null) && ok "@rhwp/core 설치 완료" || \
            warn "@rhwp/core 설치 실패. --rhwp 검증 비활성."
    fi
else
    warn "Node.js/npx를 찾을 수 없습니다."
    warn "kordoc(HWP/PDF 고급 파싱)을 사용하려면 Node.js를 먼저 설치하세요."
    warn "  macOS: brew install node"
    warn "  Ubuntu: sudo apt install nodejs npm"
    warn ""
    warn "Node.js 없이도 기본 기능(HWPX 파싱/채우기)은 정상 동작합니다."
fi

# ─── 3. MCP 서버 설정 (Cursor / Claude Code) ───

MCP_CONFIG='{
  "mcpServers": {
    "kordoc": {
      "command": "npx",
      "args": ["-y", "kordoc-mcp"]
    }
  }
}'

configure_mcp() {
    local config_file="$1"
    local tool_name="$2"

    if [ -f "$config_file" ]; then
        if grep -q '"kordoc"' "$config_file" 2>/dev/null; then
            ok "${tool_name}: kordoc MCP 이미 설정됨"
            return
        fi

        info "${tool_name}: 기존 MCP 설정에 kordoc 추가 중..."
        python3 -c "
import json, sys
try:
    with open('$config_file', 'r') as f:
        config = json.load(f)
except (json.JSONDecodeError, FileNotFoundError):
    config = {}

if 'mcpServers' not in config:
    config['mcpServers'] = {}

config['mcpServers']['kordoc'] = {
    'command': 'npx',
    'args': ['-y', 'kordoc-mcp']
}

with open('$config_file', 'w') as f:
    json.dump(config, f, indent=2, ensure_ascii=False)
    f.write('\n')
print('ok')
" && ok "${tool_name}: kordoc MCP 추가 완료 → $config_file"
    else
        info "${tool_name}: MCP 설정 파일 생성 중..."
        mkdir -p "$(dirname "$config_file")"
        echo "$MCP_CONFIG" > "$config_file"
        ok "${tool_name}: kordoc MCP 설정 생성 → $config_file"
    fi
}

if [ "$KORDOC_AVAILABLE" = true ]; then
    echo ""
    info "MCP 서버 설정 중..."

    CURSOR_MCP="${SCRIPT_DIR}/.cursor/mcp.json"
    configure_mcp "$CURSOR_MCP" "Cursor"

    CLAUDE_MCP="${SCRIPT_DIR}/.mcp.json"
    configure_mcp "$CLAUDE_MCP" "Claude Code"
fi

# ─── 4. 스킬 복사 (선택) ───

echo ""
SKILL_TARGET="$HOME/.claude/skills/k-proposal"
if [ -d "$SKILL_TARGET" ]; then
    ok "Claude Code 스킬 이미 설치됨: $SKILL_TARGET"
else
    read -p "Claude Code 스킬을 설치하시겠습니까? (~/.claude/skills/k-proposal/) [Y/n] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        mkdir -p "$SKILL_TARGET"
        cp -r "$SCRIPT_DIR/skill/"* "$SKILL_TARGET/"
        ok "스킬 설치 완료: $SKILL_TARGET"
    fi
fi

# ─── 5. 완료 ───

echo ""
echo "=========================================="
echo -e "${GREEN}  설치 완료!${NC}"
echo "=========================================="
echo ""

if [ "$KORDOC_AVAILABLE" = true ]; then
    echo "  포함된 기능:"
    echo "    ✓ HWPX 파싱/채우기/행추가"
    echo "    ✓ kordoc: HWP/PDF/XLSX/DOCX 파싱"
    echo "    ✓ kordoc MCP: AI 에이전트 직접 호출"
    echo "    ✓ 양식 자동 인식, 문서 비교"
    echo "    ✓ @rhwp/core: HWPX 빌드 결과 WASM 검증 (--rhwp)"
else
    echo "  포함된 기능:"
    echo "    ✓ HWPX 파싱/채우기/행추가"
    echo "    ✗ kordoc 미설치 (HWP/PDF 고급 파싱 비활성)"
    echo ""
    echo "  kordoc을 나중에 설치하려면:"
    echo "    1. Node.js 설치"
    echo "    2. setup.sh 다시 실행"
fi

echo ""
echo "  사용법:"
echo "    사업계획서 작성해줘 /k-proposal"
echo ""
