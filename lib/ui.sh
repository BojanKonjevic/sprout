#!/usr/bin/env bash

BOLD='\033[1m'
DIM='\033[2m'
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
MAGENTA='\033[1;35m'
CYAN='\033[0;36m'
RESET='\033[0m'

step() { printf "\n${BOLD}${MAGENTA}▸${RESET} %s\n" "$*"; }
info() { printf "  ${CYAN}ℹ${RESET}  %s\n" "$*"; }
success() { printf "  ${GREEN}✓${RESET}  %s\n" "$*"; }
warn() { printf "  ${YELLOW}⚠${RESET}  %s\n" "$*" >&2; }
error() { printf "\n  ${RED}✗  %s${RESET}\n" "$*" >&2; }
