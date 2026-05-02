#!/usr/bin/env bash

step "Applying blank template"

# Helper: substitute placeholders and write to destination
sub() { sed -e "s/__NAME__/$NAME/g" -e "s/__PKG_NAME__/$PKG_NAME/g" "$1" >"$2"; }

mkdir -p "src/$PKG_NAME" tests

cat >"src/$PKG_NAME/__init__.py" <<INIT
"""$NAME"""

__version__ = "0.1.0"
INIT

sub "$SCRIPT_DIR/templates/blank/files/main.py" "src/$PKG_NAME/main.py"
sub "$SCRIPT_DIR/templates/blank/files/__main__.py" "src/$PKG_NAME/__main__.py"
sub "$SCRIPT_DIR/templates/blank/files/tests/test_main.py" "tests/test_main.py"
