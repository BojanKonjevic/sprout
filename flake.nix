{
  description = "jumpstart — Python project scaffolder";

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
      pkgs = nixpkgs.legacyPackages.${system};
      python = pkgs.python3;
    in {
      apps.default = {
        type = "app";
        program = toString (pkgs.writeShellScript "jumpstart" ''
          export SCAFFOLDER_ROOT="${self}"
          export UV_PYTHON_DOWNLOADS=never
          export UV_PYTHON="${python}/bin/python3"
          export PATH="${python}/bin:${pkgs.uv}/bin:$PATH"
          export UV_PROJECT_ENVIRONMENT="$HOME/.cache/jumpstart-venv"
          exec uv run --no-project --with "jinja2" --with "typer" python3 "${self}/main.py" "$@"
        '');
      };

      devShells.default = pkgs.mkShell {
        packages = with pkgs; [
          python
          uv
          just
          ruff
          mypy
          git
        ];
        shellHook = ''
          export UV_PYTHON_DOWNLOADS=never
          export UV_PYTHON="${python}/bin/python3"
          # Install pip dependencies into .venv
          uv sync --quiet
          export PYTHONPATH="$PWD/src:$(echo $PWD/.venv/lib/python3.*/site-packages)"
        '';
      };
    });
}
