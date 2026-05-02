#!/usr/bin/env bash

source "$SCRIPT_DIR/lib/postgres.sh"

step "Applying fastapi template"

sub() { sed -e "s/__NAME__/$NAME/g" -e "s/__PKG_NAME__/$PKG_NAME/g" "$1" >"$2"; }
FILES="$SCRIPT_DIR/templates/fastapi/files"

# ─── Databases ────────────────────────────────────────────────────────────────
create_databases "$NAME"

# ─── Directories ──────────────────────────────────────────────────────────────
mkdir -p "src/$PKG_NAME/routes" tests alembic/versions

# ─── __init__.py ──────────────────────────────────────────────────────────────
cat >"src/$PKG_NAME/__init__.py" <<INIT
"""$NAME"""

__version__ = "0.1.0"
INIT

# ─── Verbatim source files ────────────────────────────────────────────────────
cp "$FILES/main.py" "src/$PKG_NAME/main.py"
cp "$FILES/database.py" "src/$PKG_NAME/database.py"
cp "$FILES/security.py" "src/$PKG_NAME/security.py"
cp "$FILES/models.py" "src/$PKG_NAME/models.py"
touch "src/$PKG_NAME/routes/__init__.py"
cp "$FILES/alembic/script.py.mako" "alembic/script.py.mako"
cp "$FILES/tests/test_main.py" "tests/test_main.py"
cp "$FILES/.env.example" ".env.example"

# ─── Substituted files ────────────────────────────────────────────────────────
sub "$FILES/settings.py" "src/$PKG_NAME/settings.py"
sub "$FILES/alembic.ini" "alembic.ini"
sub "$FILES/alembic/env.py" "alembic/env.py"
sub "$FILES/tests/conftest.py" "tests/conftest.py"
sub "$FILES/.env" ".env"
