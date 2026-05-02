#!/usr/bin/env bash

generate_pyproject() {
  local runtime_deps

  if [ "$TEMPLATE" = "fastapi" ]; then
    runtime_deps='"fastapi",
  "uvicorn[standard]",
  "sqlalchemy[asyncio]",
  "alembic",
  "asyncpg",
  "pydantic-settings",
  "passlib[bcrypt]",
  "python-jose[cryptography]",
  "email-validator",
  "python-multipart",
  "python-dotenv",'
  else
    runtime_deps='"python-dotenv",'
  fi

  cat >pyproject.toml <<PYPROJECT
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "$NAME"
version = "0.1.0"
description = ""
requires-python = ">=3.13"
dependencies = [
  $runtime_deps
]

[dependency-groups]
dev = [
  "pytest>=8",
  "pytest-cov",
  "pytest-asyncio",
  "httpx",
  "mypy",
  "ipython",
]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
# Belt-and-suspenders alongside PYTHONPATH: pytest inserts src/ into sys.path
# before stdlib, so same-named stdlib modules (e.g. 'email') can't shadow ours.
pythonpath = ["src"]

[tool.ruff]
line-length = 88
exclude = ["alembic/", ".venv/"]

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "ANN", "SIM"]

[tool.mypy]
strict = true
PYPROJECT

  if [ "$TEMPLATE" = "fastapi" ]; then
    cat >>pyproject.toml <<'EOF'

[[tool.mypy.overrides]]
module = ["jose.*", "passlib.*"]
ignore_missing_imports = true
ignore_errors = true
EOF
  fi

  success "pyproject.toml"
}

generate_justfile() {
  local just_run extra_just_targets

  if [ "$TEMPLATE" = "fastapi" ]; then
    just_run="uvicorn ${PKG_NAME}.main:app --reload"
    extra_just_targets="
migrate msg=\"\":
    alembic revision --autogenerate -m \"{{msg}}\"
upgrade:
    alembic upgrade head
downgrade:
    alembic downgrade -1
db-drop:
    dropdb $NAME
db-drop-test:
    dropdb ${NAME}_test
db-create:
    createdb $NAME && createdb ${NAME}_test && just upgrade
db-reset:
    -dropdb $NAME
    -dropdb ${NAME}_test
    createdb $NAME && createdb ${NAME}_test && just upgrade"
  else
    just_run="python -m $PKG_NAME"
    extra_just_targets=""
  fi

  cat >justfile <<JUSTFILE
test:
    pytest -v
cov:
    pytest --cov=src --cov-report=term-missing
lint:
    ruff check .
fmt:
    ruff format .
check:
    mypy src/
run:
    $just_run
$extra_just_targets
JUSTFILE

  success "justfile"
}

generate_flake() {
  local shell_help

  if [ "$TEMPLATE" = "fastapi" ]; then
    shell_help='printf "  \033[34m%-26s\033[0m %s\n" "just run" "start dev server (--reload)"
          printf "  \033[34m%-26s\033[0m %s\n" "just migrate \"msg\"" "generate migration"
          printf "  \033[34m%-26s\033[0m %s\n" "just upgrade" "apply migrations"
          printf "  \033[34m%-26s\033[0m %s\n" "just downgrade" "roll back one step"
          printf "  \033[34m%-26s\033[0m %s\n" "just db-drop" "delete the main db"
          printf "  \033[34m%-26s\033[0m %s\n" "just db-drop-test" "delete the test db"
          printf "  \033[34m%-26s\033[0m %s\n" "just db-create" "create both dbs + migrate"
          printf "  \033[34m%-26s\033[0m %s\n" "just db-reset" "recreate both dbs + migrate"'
  else
    shell_help='printf "  \033[34m%-26s\033[0m %s\n" "just run" "run the app"'
  fi

  cat >flake.nix <<FLAKE
{
  description = "$NAME — Python dev environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = {
    self,
    nixpkgs,
    flake-utils,
  }:
    flake-utils.lib.eachDefaultSystem (system: let
      pkgs = nixpkgs.legacyPackages.\${system};
      pythonVersion = "313"; # ← python version
      python = pkgs."python\${pythonVersion}";
    in {
      devShells.default = pkgs.mkShell {
        packages = with pkgs; [
          python
          uv
          just
          pre-commit
          git
          ripgrep
          fd
          stdenv.cc.cc.lib
          ruff
        ];

        shellHook = ''
          # libstdc++ must be set before uv sync so native extensions
          # (greenlet, asyncpg, cryptography) link correctly at compile + runtime.
          export LD_LIBRARY_PATH="\${pkgs.stdenv.cc.cc.lib}/lib:\$LD_LIBRARY_PATH"

          # Lock uv to the Nix-managed Python — never download a separate one.
          export UV_PYTHON_DOWNLOADS=never
          export UV_PYTHON="\${python}/bin/python3"

          # src/ layout: package importable without an editable install.
          export PYTHONPATH="\$PWD/src"

          # Sync deps on every entry — no-op when uv.lock is unchanged (<50ms).
          uv sync --quiet

          # Prepend venv so pytest/ruff/mypy from uv win over any Nix copies.
          export PATH="\$PWD/.venv/bin:\$PATH"

          # Install git hooks once (silently skipped before git init).
          if [ -f .pre-commit-config.yaml ] && [ ! -f .git/hooks/pre-commit ]; then
            pre-commit install --quiet 2>/dev/null || true
          fi

          printf "\n  \033[1;35m$NAME\033[0m \033[2mdev shell\033[0m  \033[36m\$(python3 --version)\033[0m\n\n"
          printf "  \033[34m%-26s\033[0m %s\n" "just test"  "run tests"
          printf "  \033[34m%-26s\033[0m %s\n" "just cov"   "coverage report"
          printf "  \033[34m%-26s\033[0m %s\n" "just lint"  "ruff check"
          printf "  \033[34m%-26s\033[0m %s\n" "just fmt"   "ruff format"
          printf "  \033[34m%-26s\033[0m %s\n" "just check" "mypy"
          $shell_help
          printf "\n"
        '';
      };
    });
}
FLAKE

  success "flake.nix"
}
