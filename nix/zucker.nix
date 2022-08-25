{ lib
, buildPythonPackage
, pythonOlder
, requests
, aiohttp
, colored
, pytestCheckHook
, pytest-asyncio
, pytest-cov
, hypothesis
}:

buildPythonPackage {
  pname = "zucker";
  version = "0.1.0";
  src = ../.;
  disabled = pythonOlder "3.7";

  checkInputs = [
    requests aiohttp colored
    pytestCheckHook pytest-asyncio pytest-cov hypothesis
  ];

  # Currently doesn't work because of empty runtime dependencies.
  # pythonImportsCheck = [ "zucker" ];
}
