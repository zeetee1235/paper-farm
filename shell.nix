{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  name = "paper-farm";

  packages = with pkgs; [
    # Python runtime + uv (uv manages the venv and dependencies)
    python312
    uv

    # Rust toolchain — required to build the DocStruct submodule
    cargo
    rustc
    rustfmt
    clippy

    # System libraries used by Python OCR dependencies
    poppler_utils   # pdf2image backend
    tesseract       # pytesseract backend
    libjpeg         # Pillow
    zlib

    # Utilities
    git
    curl            # health-check Ollama, etc.
  ];

  shellHook = ''
    # Create / reuse the uv-managed virtual environment
    if [ ! -d .venv ]; then
      uv sync
    fi
    source .venv/bin/activate

    # Point pytesseract at the nix-provided binary
    export TESSDATA_PREFIX="${pkgs.tesseract}/share/tessdata"

    # Make the DocStruct binary discoverable once built
    export DOCSTRUCT_BIN="$PWD/external/DocStruct/target/release/docstruct"

    echo "paper-farm dev shell ready"
    echo "  Python : $(python --version)"
    echo "  uv     : $(uv --version)"
    echo "  Cargo  : $(cargo --version)"
  '';
}
