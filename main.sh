#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="${SCAFFOLDER_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"

# shellcheck source=lib/ui.sh
source "$SCRIPT_DIR/lib/ui.sh"
# shellcheck source=lib/validate.sh
source "$SCRIPT_DIR/lib/validate.sh"
# shellcheck source=lib/prompt.sh
source "$SCRIPT_DIR/lib/prompt.sh"
# shellcheck source=lib/generate.sh
source "$SCRIPT_DIR/lib/generate.sh"
# shellcheck source=lib/nix.sh
source "$SCRIPT_DIR/lib/nix.sh"

# ─── Arguments ────────────────────────────────────────────────────────────────
if [ -z "${1:-}" ]; then
	error "Usage: $0 <project-name>"
	exit 1
fi

NAME="$1"
PKG_NAME="${NAME//-/_}"
export NAME PKG_NAME SCRIPT_DIR

# ─── Validate ─────────────────────────────────────────────────────────────────
validate_name "$NAME" "$PKG_NAME"

# ─── Prompt ───────────────────────────────────────────────────────────────────
prompt_template
export TEMPLATE

echo ""
step "Creating Python project '$NAME'  (template: $TEMPLATE)"

# ─── Create and enter project directory ───────────────────────────────────────
mkdir -p "$NAME"
cd "$NAME"

# ─── Apply common files ───────────────────────────────────────────────────────
# shellcheck source=templates/_common/apply.sh
source "$SCRIPT_DIR/templates/_common/apply.sh"

# ─── Apply template ───────────────────────────────────────────────────────────
# shellcheck source=templates/blank/apply.sh
source "$SCRIPT_DIR/templates/$TEMPLATE/apply.sh"

# ─── Generate config files ────────────────────────────────────────────────────
generate_pyproject
generate_justfile
generate_flake

# ─── Lock ─────────────────────────────────────────────────────────────────────
lock_flake

# ─── Done ─────────────────────────────────────────────────────────────────────
echo ""
success "Project '$NAME' created!  (template: $TEMPLATE)"
echo ""
echo "  cd $NAME"
echo "  git init && git add ."
if [ "$TEMPLATE" = "fastapi" ]; then
	echo ""
	info "When you're ready to add auth:"
	echo "    1. Define User + RefreshToken in models.py"
	echo "    2. Add src/$PKG_NAME/dependencies.py  (get_current_user)"
	echo "    3. Add src/$PKG_NAME/routes/auth.py"
	echo "    4. Activate the client fixture in tests/conftest.py"
	echo "    5. just migrate 'add users' && just upgrade"
fi
