#!/usr/bin/env bash

create_databases() {
	local name="$1"

	if ! command -v psql &>/dev/null; then
		error "psql not found — cannot create Postgres databases."
		exit 1
	fi

	for dbname in "$name" "${name}_test"; do
		if psql -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$dbname'" | grep -q 1; then
			warn "Postgres database '$dbname' already exists, skipping."
		else
			createdb "$dbname"
			success "Created Postgres database '$dbname'."
		fi
	done
}
