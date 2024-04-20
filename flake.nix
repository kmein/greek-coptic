{
  description = "Analysing the Coptic spellings of Greek loan words";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs";
    ddglc-attestations.url = "https://c.krebsco.de/ddglc-attestations.csv";

    ddglc-attestations.flake = false;
  };

  outputs = { self, nixpkgs, ddglc-attestations }:
  let
    system = "x86_64-linux";
    pkgs = nixpkgs.legacyPackages.${system};
    lib = nixpkgs.lib;
    pythonInstallation = pkgs.python3.withPackages (p: [
      p.pandas
      p.jupyter
      p.matplotlib
      p.seaborn
      p.tabulate
      p.papermill
    ]);
  in {
    apps.${system} = {
      jupyter = {
        type = "app";
        program = toString (pkgs.writers.writeDash "jupyter" ''
          PATH=${nixpkgs.lib.makeBinPath [pythonInstallation]} \
          ATTESTATIONS_CSV=${ddglc-attestations} \
          jupyter notebook
        '');
      };
    };

    packages.${system} = {
      assets = pkgs.runCommand "assets" {} ''
        PATH=$PATH:${nixpkgs.lib.makeBinPath [pythonInstallation]} \
        ATTESTATIONS_CSV=${ddglc-attestations} \
        papermill ${./greek-coptic.ipynb} /dev/null

        for figure in assets/*.svg; do
          ${pkgs.inkscape}/bin/inkscape -D --export-latex --export-filename="assets/$(basename "$figure" .svg).pdf" "$figure"
        done

        # make table page break footer empty. original one is ugly and in english
        ${pkgs.gnused}/bin/sed -i '/endhead/,/endfoot/{//!d}' assets/table-*.tex

        mkdir -p $out
        cp assets/*{md,html,svg,tex,pdf} $out/
      '';
    };
  };
}
