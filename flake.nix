{
  description = "zucker";

  inputs.nixpkgs.url = "nixpkgs/nixos-21.11";
  inputs.flake-utils.url = "github:numtide/flake-utils";

  outputs = { self, nixpkgs, flake-utils }: (flake-utils.lib.eachDefaultSystem (system:
    let
      pkgs = import nixpkgs { inherit system; };
    in
    rec {
      packages = {
        zucker = pkgs.python39Packages.callPackage ./nix/zucker.nix {};

        devEnv = pkgs.python39.withPackages(ps: with ps; [
          # Optional runtime dependencies
          requests aiohttp colored
          # Release tools
          build twine
          # Testing, linting, formatting and type checking
          pytest pytest-asyncio pytest-cov hypothesis
          mypy types-requests
          black isort
          # Documentation
          sphinx sphinx_rtd_theme
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

      checks = let
       mkCheckDerivation = definition: pkgs.stdenv.mkDerivation ({
           inherit (packages.zucker) version src;
           dontBuild = true;
           doCheck = true;

            installPhase = ''
              echo "This derivation just runs tests." > $out
            '';
         } // definition);
      in {
        inherit (packages) zucker;

        # This derivation runs the black and isort checks.
        style = mkCheckDerivation {
          pname = "zucker-style-tests";
          checkInputs = [(pkgs.python39.withPackages (ps: with ps; [
            black isort
          ]))];
          checkPhase = ''
            black --check tests/ zucker/
            isort --check tests/ zucker/
          '';
        };

        # Run mypy on the entire codebase.
        types = mkCheckDerivation {
          pname = "zucker-type-checks";
          checkInputs =  [(pkgs.python39.withPackages (ps: with ps; [
            pytest pytest-asyncio hypothesis mypy types-requests aiohttp
          ]))];
          checkPhase = ''
            mypy tests/ zucker/
          '';
        };
      };

      devShell = packages.devEnv.env;
    }
  ));
}
