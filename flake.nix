{
  description = "Python project scaffolder";

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
    in {
      apps.default = {
        type = "app";
        meta.description = "Creates a new Python project from template";
        program = toString (pkgs.writeShellScript "new-python-project" ''
          export SCAFFOLDER_ROOT="${self}"
          export PATH="${pkgs.uv}/bin:$PATH"
          exec ${pkgs.bash}/bin/bash "${self}/main.sh" "$@"
        '');
      };
    });
}
