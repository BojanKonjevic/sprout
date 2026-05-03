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
      python = pkgs.python3.withPackages (ps: [ps.jinja2 ps.mypy]);
    in {
      apps.default = {
        type = "app";
        meta.description = "Creates a new Python project from template";
        program = toString (pkgs.writeShellScript "sprout" ''
          export SCAFFOLDER_ROOT="${self}"
          export PATH="${pkgs.uv}/bin:$PATH"
          exec ${python}/bin/python3 "${self}/main.py" "$@"
        '');
      };

      devShells.default = pkgs.mkShell {
        packages = with pkgs; [
          python
          uv
          ruff
          just
        ];
      };
    });
}
