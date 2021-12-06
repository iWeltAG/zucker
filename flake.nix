{
  description = "zucker";

  inputs.nixpkgs.url = "nixpkgs/nixpkgs-unstable";
  inputs.flake-utils.url = "github:numtide/flake-utils";

  outputs = { self, nixpkgs, flake-utils }: (flake-utils.lib.eachDefaultSystem (system:
    let
      pkgs = import nixpkgs { inherit system; };

      devEnv = pkgs.python39.withPackages(ps: with ps; [
        mypy requests aiohttp colored pytest pytest-cov hypothesis sphinx sphinx_rtd_theme black isort
      ]);
    in
    rec {
      packages = { inherit devEnv; };
      defaultPackage = devEnv;

      devShell = devEnv.env;
    }
  ));
}
