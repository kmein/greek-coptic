{
  fetchPypi,
  buildPythonPackage,
  matplotlib,
  scipy,
  numpy,
  ...
}:
buildPythonPackage rec {
  pname = "matplotlib-venn";
  version = "0.11.10";
  src = fetchPypi {
    inherit pname version;
    hash = "sha256-kNDPsnnF273339ciwOJRWjf1NelJvK0XRIO8d343LmU=";
  };
  propagatedBuildInputs = [scipy numpy matplotlib];
  doCheck = false;
}
