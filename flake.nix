{
  description = "zucker";

  inputs.nixpkgs.url = "nixpkgs/nixpkgs-unstable";
  inputs.flake-utils.url = "github:numtide/flake-utils";

  outputs = { self, nixpkgs, flake-utils }: (flake-utils.lib.eachDefaultSystem (system:
    let
      pkgs = import nixpkgs { inherit system; };
    in
    rec {
      packages = {
        zucker = pkgs.python39Packages.callPackage ./nix/zucker.nix {};

        devEnv = pkgs.python39.withPackages(ps: with ps; [
          mypy requests aiohttp colored pytest pytest-cov hypothesis sphinx sphinx_rtd_theme black isort
        ]);

        docs = pkgs.stdenv.mkDerivation {
          inherit (packages.zucker) version src;
          pname = "zucker-docs";

          buildInputs = [
            (pkgs.python39.withPackages (ps: with ps; [
              sphinx sphinx_rtd_theme
            ]))
          ];
          buildPhase = ''
            sphinx-build -b html docs public
            touch public/.nojekyll
          '';

          installPhase = ''
            cp -r public $out
          '';
        };
      };
      defaultPackage = packages.zucker;

      checks = {
        inherit (packages) zucker;

        # This derivation runs the black and isort checks.
        style = pkgs.stdenv.mkDerivation {
          inherit (packages.zucker) version src;
          pname = "zucker-style-tests";
          dontBuild = true;

          installPhase = ''
            echo "This derivation just runs tests." > $out
          '';

          doCheck = true;
          checkInputs = with pkgs.python39Packages; [
            black isort
          ];
          checkPhase = ''
            black --check tests/ zucker/
            isort --check tests/ zucker/
          '';
        };
      };

      devShell = packages.devEnv.env;
    }
  ));
}
