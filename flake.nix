{
  description = "sprout — Python project scaffolder";

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
      python = pkgs.python3.withPackages (ps: [ps.jinja2]);
    in {
      apps.default = {
        type = "app";
        program = toString (pkgs.writeShellScript "sprout" ''
          export SCAFFOLDER_ROOT="${self}"
          export UV_PYTHON_DOWNLOADS=never
          export UV_PYTHON="${python}/bin/python3"
          # Ensure python3 is available in the script's PATH
          export PATH="${python}/bin:${pkgs.uv}/bin:$PATH"
          exec python3 "${self}/main.py" "$@"
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
