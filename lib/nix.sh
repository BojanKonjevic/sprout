#!/usr/bin/env bash

lock_flake() {
	echo ""
	step "Locking Nix flake inputs..."
	nix flake lock
	success "flake.lock written."
}
