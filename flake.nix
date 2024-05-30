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
    zip-font = name: arguments: let
      directory = pkgs.fetchzip arguments;
    in
      pkgs.runCommand name {} ''
        mkdir -p $out/share/fonts/{truetype,opentype,woff}
        ${pkgs.findutils}/bin/find ${directory} -name '*.ttf' -exec install '{}' $out/share/fonts/truetype \;
        ${pkgs.findutils}/bin/find ${directory} -name '*.otf' -exec install '{}' $out/share/fonts/opentype \;
        ${pkgs.findutils}/bin/find ${directory} -name '*.woff' -exec install '{}' $out/share/fonts/woff \;
      '';

    pythonInstallation = pkgs.python3.withPackages (p: [
      p.pandas
      p.jupyter
      p.matplotlib
      p.seaborn
      p.tabulate
      p.papermill
      p.networkx
      p.scikit-learn
      p.plotly
      p.scipy
      self.packages.${system}.matplotlib-venn
    ]);

    antinoou = zip-font "Antinoou" {
      url = "https://www.evertype.com/fonts/coptic/AntinoouFont.zip";
      sha256 = "0jwihj08n4yrshcx07dnaml2x9yws6dgyjkvg19jqbz17drbp3sw";
      stripRoot = false;
    };

    fontsConf = pkgs.makeFontsConf {
      fontDirectories = [ antinoou ];
    };
  in {
    apps.${system} = {
      jupyter = {
        type = "app";
        program = toString (pkgs.writers.writeDash "jupyter" ''
          ANTINOOU_FONT=${antinoou}/share/fonts/truetype/Antinoou.ttf \
          PATH=${nixpkgs.lib.makeBinPath [pythonInstallation]} \
          ATTESTATIONS_CSV=${ddglc-attestations} \
          jupyter notebook
        '');
      };
    };

    packages.${system} = {
      matplotlib-venn = pkgs.python3Packages.callPackage ./matplotlib-venn.nix {};
      antinoou = antinoou;
      assets = pkgs.runCommand "assets" {} ''
        ANTINOOU_FONT=${antinoou}/share/fonts/truetype/Antinoou.ttf \
        FONTCONFIG_FILE=${fontsConf} \
        PATH=$PATH:${nixpkgs.lib.makeBinPath [pythonInstallation]} \
        ATTESTATIONS_CSV=${ddglc-attestations} \
        papermill ${./greek-coptic.ipynb} /dev/null

        FONTCONFIG_FILE=${fontsConf} \
        ${pkgs.fontconfig}/bin/fc-list > assets/fontconfig.txt

        # make table page break footer empty. original one is ugly and in english
        ${pkgs.gnused}/bin/sed -i '/endhead/,/endfoot/{//!d}' assets/table-*.tex

        mkdir -p $out
        cp assets/*{txt,md,csv,html,svg,tex,pdf} $out/
      '';
    };
  };
}
