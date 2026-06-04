#!/usr/bin/env bash
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

ok()   { echo -e "${GREEN}✓${NC} $1"; }
info() { echo -e "${CYAN}→${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC}  $1"; }
fail() { echo -e "${RED}✗${NC} $1"; exit 1; }
section() { echo -e "\n${BOLD}$1${NC}"; echo "────────────────────────────"; }

echo -e "${BOLD}"
echo "  ░█▀▀░█░█░█▀▄░█▀▀░█░█░█▀▄░█▀█"
echo "  ░█░░░█░█░█▀▄░▀▀█░█░█░█▀▄░█▀█"
echo "  ░▀▀▀░▀▀▀░▀░▀░▀▀▀░▀▀▀░▀░▀░▀░▀"
echo "  Dzeck — Install Script"
echo -e "${NC}"

# ────────────────────────────
section "1. Cek Rust & Cargo"
# ────────────────────────────
if command -v cargo &>/dev/null; then
    CARGO_VER=$(cargo --version)
    ok "Cargo ditemukan: $CARGO_VER"
else
    warn "Cargo tidak ditemukan. Mencoba install via rustup..."
    if command -v curl &>/dev/null; then
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable
        source "$HOME/.cargo/env"
        ok "Rust berhasil diinstall: $(cargo --version)"
    else
        fail "curl tidak tersedia. Install Rust manual: https://rustup.rs"
    fi
fi

# ────────────────────────────
section "2. Cek Python"
# ────────────────────────────
if command -v python3 &>/dev/null; then
    PY_VER=$(python3 --version)
    ok "Python ditemukan: $PY_VER"
else
    fail "Python 3 tidak ditemukan. Install Python 3.8+ terlebih dahulu."
fi

# ────────────────────────────
section "3. Install Python Dependencies"
# ────────────────────────────
PIP_CMD=""
if command -v pip &>/dev/null; then
    PIP_CMD="pip"
elif command -v pip3 &>/dev/null; then
    PIP_CMD="pip3"
elif python3 -m pip --version &>/dev/null 2>&1; then
    PIP_CMD="python3 -m pip"
else
    fail "pip tidak ditemukan. Install pip terlebih dahulu."
fi

info "Menggunakan: $PIP_CMD"
info "Menginstall Flask..."
$PIP_CMD install flask --quiet
ok "Flask berhasil diinstall: $(python3 -c "import importlib.metadata; print(importlib.metadata.version('flask'))" 2>/dev/null || echo 'OK')"

# ────────────────────────────
section "4. Build Dzeck (Rust)"
# ────────────────────────────
if [ ! -f "Cargo.toml" ]; then
    fail "Cargo.toml tidak ditemukan. Jalankan install.sh dari root direktori project."
fi

if [ -f "target-build/debug/obscura" ]; then
    ok "Binary sudah ada di target-build/debug/obscura — skip build."
    info "Jalankan 'CARGO_TARGET_DIR=target-build cargo build' untuk rebuild."
else
    info "Memulai build Dzeck (mungkin 3–5 menit untuk pertama kali)..."
    CARGO_TARGET_DIR=target-build cargo build 2>&1 | grep -E '(Compiling|Finished|error|warning.*unused)' || true
    if [ -f "target-build/debug/obscura" ]; then
        ok "Build berhasil: target-build/debug/obscura"
    else
        fail "Build gagal. Jalankan: CARGO_TARGET_DIR=target-build cargo build"
    fi
fi

# ────────────────────────────
section "5. Cek Environment Variables"
# ────────────────────────────
MISSING_ENV=0
if [ -z "$AI_BASE_URL" ]; then
    warn "AI_BASE_URL belum diset  (diperlukan untuk fitur AI Agent)"
    MISSING_ENV=1
else
    ok "AI_BASE_URL = $AI_BASE_URL"
fi

if [ -z "$AI_API_KEY" ]; then
    warn "AI_API_KEY belum diset   (diperlukan untuk fitur AI Agent)"
    MISSING_ENV=1
else
    ok "AI_API_KEY  = sk-****${AI_API_KEY: -4}"
fi

if [ "$MISSING_ENV" -eq 1 ]; then
    echo ""
    echo -e "  ${YELLOW}Set environment variables dengan:${NC}"
    echo -e "  ${CYAN}export AI_BASE_URL=https://your-ai-api.com${NC}"
    echo -e "  ${CYAN}export AI_API_KEY=sk-your-api-key${NC}"
fi

# ────────────────────────────
section "6. Verifikasi Akhir"
# ────────────────────────────
ok "Obscura binary  : $(./target-build/debug/obscura --version 2>/dev/null || echo 'OK')"
ok "Flask           : ready"
ok "Python          : $(python3 --version)"
ok "Cargo           : $(cargo --version)"

echo ""
echo -e "${GREEN}${BOLD}✅ Semua dependency berhasil diinstall!${NC}"
echo ""
echo -e "  Jalankan web UI dengan:"
echo -e "  ${CYAN}python3 app.py${NC}"
echo ""
echo -e "  Atau gunakan binary langsung:"
echo -e "  ${CYAN}./target-build/debug/obscura fetch https://example.com --dump text${NC}"
echo ""
