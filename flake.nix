{
  description = "zucker";

  inputs.nixpkgs.url = "nixpkgs/nixpkgs-unstable";
  inputs.nixpkgs-stable.url = "nixpkgs/release-22.05";
  inputs.flake-utils.url = "github:numtide/flake-utils";

  outputs = { self, nixpkgs, nixpkgs-stable, flake-utils }: (flake-utils.lib.eachDefaultSystem (system:
    let
      pkgs = import nixpkgs { inherit system; };
      stablePkgs = import nixpkgs-stable { inherit system; };

      python = pkgs.python310.override {
        packageOverrides = self: super: {
          mypy = super.mypy.overridePythonAttrs (attrs: {
            version = "master-20220825";
            src = pkgs.fetchFromGitHub {
              owner = "python";
              repo = "mypy";
              rev = "d9750c606c047a41edd8d6482310858f7bf955b3";
              hash = "sha256-Sg7mSR+JpWBpT9UcIs+SHVQbeNGv75v68KD688hAMPI=";
            };

            # The PR that the patch in nixpkgs targets has already been merged:
            # https://github.com/NixOS/nixpkgs/blob/f034b5693a26625f56068af983ed7727a60b5f8b/pkgs/development/python-modules/mypy/default.nix#L28-L33
            patches = [ ];

            buildInputs = attrs.buildInputs ++ [
              self.types-setuptools
              self.types-psutil
            ];
          });

          types-psutil = self.buildPythonPackage rec {
            pname = "types-psutil";
            version = "5.9.5";

            src = self.fetchPypi {
              inherit version;
              pname = "types-psutil";
              sha256 = "sha256-vvkd4Ja3f/e8OpK6/kZu5V+EIobB1zRli3wmslkHglM=";
            };

            pythonImportsCheck = [ "psutil-stubs" ];
          };

          zucker = self.callPackage ./nix/zucker.nix {};
        };
      };
    in
    rec {
      packages = {
        default = python.pkgs.zucker;

        devEnv = python.withPackages(ps: with ps; [
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
          inherit (packages.default) version src;
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

      checks = let
       mkCheckDerivation = definition: pkgs.stdenv.mkDerivation ({
           inherit (packages.default) version src;
           dontBuild = true;
           doCheck = true;
           installPhase = ''
             echo "This derivation just runs tests." > $out
           '';
         } // definition);
      in {
        zucker-python38 = stablePkgs.python38Packages.callPackage ./nix/zucker.nix { };
        zucker-python39 = stablePkgs.python39Packages.callPackage ./nix/zucker.nix { };
        zucker-python310 = stablePkgs.python310Packages.callPackage ./nix/zucker.nix { };

        # This derivation runs the black and isort checks.
        style = mkCheckDerivation {
          pname = "zucker-style-tests";
          checkInputs = [(python.withPackages (ps: with ps; [
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
          checkInputs =  [(python.withPackages (ps: with ps; [
            pytest pytest-asyncio hypothesis mypy types-requests aiohttp
          ]))];
          checkPhase = ''
            mypy --enable-recursive-aliases tests/ zucker/
          '';
        };
      };

      devShells.default = packages.devEnv.env;
    }
  ));
}
