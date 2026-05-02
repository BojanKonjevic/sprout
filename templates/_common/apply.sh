#!/usr/bin/env bash

step "Copying common files"

cp "$SCRIPT_DIR/templates/_common/gitignore" .gitignore
cp "$SCRIPT_DIR/templates/_common/pre-commit-config.yaml" .pre-commit-config.yaml
cp "$SCRIPT_DIR/templates/_common/envrc" .envrc
direnv allow
