#!/usr/bin/env bash

prompt_template() {
	echo ""
	printf "  Select a template:\n\n"
	printf "    ${CYAN}1)${RESET} blank    — dev tools only (pytest, ruff, mypy)\n"
	printf "    ${CYAN}2)${RESET} fastapi  — FastAPI + SQLAlchemy + Alembic + asyncpg\n"
	echo ""

	while true; do
		read -rp "  Template [1/2]: " TEMPLATE_CHOICE
		case "$TEMPLATE_CHOICE" in
		1 | blank)
			TEMPLATE="blank"
			break
			;;
		2 | fastapi)
			TEMPLATE="fastapi"
			break
			;;
		*) warn "Please enter 1 or 2." ;;
		esac
	done
}
