#!/usr/bin/env bash

STDLIB_RESERVED="test sys os io re json math time datetime collections itertools
  functools pathlib typing abc ast copy csv enum http logging operator random
  socket string struct threading types unittest urllib uuid warnings xml email
  html queue array bisect calendar cmath contextlib contextvars dataclasses
  decimal difflib dis filecmp fnmatch fractions gc getopt getpass gettext glob
  graphlib hashlib heapq hmac inspect ipaddress keyword locale marshal mimetypes
  mmap numbers pickle pprint profile pstats readline runpy select selectors
  shelve shlex shutil signal site smtplib sqlite3 stat statistics subprocess
  symbol symtable sysconfig tabnanny tarfile tempfile textwrap token tokenize
  tomllib trace traceback tracemalloc tty unicodedata venv weakref webbrowser
  zipapp zipfile zipimport zlib zoneinfo"

validate_name() {
	local name="$1"
	local pkg_name="$2"

	if [ -d "$name" ]; then
		error "Directory '$name' already exists."
		exit 1
	fi

	if ! command -v uv &>/dev/null; then
		error "'uv' is not installed or not in PATH."
		exit 1
	fi

	if ! [[ "$name" =~ ^[a-zA-Z][a-zA-Z0-9_-]*$ ]]; then
		error "Invalid project name '$name'."
		info "Must start with a letter; only letters, numbers, hyphens, underscores allowed."
		exit 1
	fi

	for reserved in $STDLIB_RESERVED; do
		if [ "$pkg_name" = "$reserved" ]; then
			error "'$pkg_name' shadows a Python stdlib module."
			info "Suggestion: '${name}-app'  or  'my-${name}'"
			exit 1
		fi
	done
}
