#!/usr/bin/env python3
"""
map_extract.py — Extract text-free and/or text-only images from a CAD/map PDF.

Usage examples:
    python map_extract.py input.pdf --both ./output/
    python map_extract.py input.pdf --no-text map_clean.png --dpi 72
    python map_extract.py input.pdf --text-only labels.png --dpi 150 -v
    python map_extract.py input.pdf --both . --dpi 100 -v

Requirements:
    pip install PyMuPDF Pillow numpy
    pdftoppm (Poppler) — recommended for best color accuracy; falls back to PyMuPDF
    Install: sudo dnf install poppler-utils  OR  sudo apt install poppler-utils
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

import fitz
import numpy as np
from PIL import Image

# Layer name substrings that indicate text/annotation content (case-insensitive).
# Extend this list if your PDF has text on differently-named layers.
TEXT_LAYER_KEYWORDS = [
    "text",
    "anno",
    "label",
    "dimension",
    "arearon",
    "رقم",
    "blocks numbers",
    "g-anno-text",
    "a-text",
]


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def find_text_layers(doc):
    """Return list of OCG xrefs whose names suggest text/annotation content."""
    result = []
    for xref, info in doc.get_ocgs().items():
        name = info["name"].lower()
        if any(k in name for k in TEXT_LAYER_KEYWORDS):
            result.append((xref, info["name"]))
    return result


def strip_bt_et(doc, page):
    """
    Remove all BT...ET operator blocks from page content streams.
    These are the PDF text-drawing commands. Returns count of blocks removed.
    """
    total = 0
    for xref in page.get_contents():
        raw = doc.xref_stream(xref)
        cleaned = re.sub(rb"BT\b.*?\bET\b", b"", raw, flags=re.DOTALL)
        removed = len(re.findall(rb"BT\b", raw)) - len(re.findall(rb"BT\b", cleaned))
        if removed:
            doc.update_stream(xref, cleaned)
            total += removed
    return total


def widen_lines(doc, scale=2.0, min_width=0.5):
    """
    Multiply every line-width operator (`w`) in the content stream by `scale`,
    with a floor of `min_width` points. Hairlines (width=0) become `min_width`.
    Operates on a copy — call on the doc you are about to render.
    """
    page = doc[0]
    def replace(m):
        val = float(m.group(1))
        new_val = max(val * scale, min_width) if val > 0 else min_width
        return f"{new_val:.4f} w".encode()

    for xref in page.get_contents():
        raw = doc.xref_stream(xref)
        patched = re.sub(rb"(\d+(?:\.\d+)?)\s+w\b", replace, raw)
        if patched != raw:
            doc.update_stream(xref, patched)


def render_to_array(doc, dpi):
    """
    Render the first page of doc to an RGB numpy array.
    Prefers Poppler (pdftoppm) for better color accuracy with CAD PDFs.
    Falls back to PyMuPDF if Poppler is not installed.
    """
    if shutil.which("pdftoppm"):
        # Save modified doc to a temp file so pdftoppm can read it
        with tempfile.TemporaryDirectory() as tmp:
            tmp_pdf = os.path.join(tmp, "page.pdf")
            tmp_out = os.path.join(tmp, "out")
            doc.save(tmp_pdf)
            subprocess.run(
                ["pdftoppm", "-r", str(dpi), "-png", "-f", "1", "-l", "1",
                 tmp_pdf, tmp_out],
                check=True, capture_output=True,
            )
            out_png = tmp_out + "-1.png"
            arr = np.array(Image.open(out_png).convert("RGB"))
        return arr

    # Fallback: PyMuPDF renderer
    page = doc[0]
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
    return arr.copy()


# ---------------------------------------------------------------------------
# Main extraction functions
# ---------------------------------------------------------------------------

def build_no_text(pdf_path, dpi, verbose, line_scale=1.0):
    """
    Render the PDF with all text removed:
      1. Turn off OCG layers whose names match text keywords.
      2. Strip BT..ET operator blocks from the content stream.
      3. Optionally scale all line widths by `line_scale`.
    Returns the rendered image as an RGB numpy array.
    """
    doc = fitz.open(pdf_path)

    # Step 1 — OCG layer suppression
    text_layers = find_text_layers(doc)
    if text_layers:
        off_xrefs = [x for x, _ in text_layers]
        doc.set_layer(-1, off=off_xrefs)
        if verbose:
            print(f"  OCG: turned off {len(off_xrefs)} text layer(s):")
            for xref, name in text_layers:
                print(f"       [{xref}] {name}")
    elif verbose:
        print("  OCG: no text layers found (skipping OCG step)")

    # Step 2 — content stream stripping (catches non-OCG text)
    page = doc[0]
    removed = strip_bt_et(doc, page)
    if verbose:
        print(f"  Stream: removed {removed} BT..ET text block(s)")

    # Step 3 — optional line widening
    if line_scale != 1.0:
        widen_lines(doc, scale=line_scale)
        if verbose:
            print(f"  Lines: widened by {line_scale}×")

    arr = render_to_array(doc, dpi)
    if verbose:
        print(f"  Rendered: {arr.shape[1]}x{arr.shape[0]} px at {dpi} DPI")
    return arr


def build_text_only(pdf_path, no_text_arr, dpi, verbose):
    """
    Pixel-diff between the full render and the no-text render.
    Pixels that changed = text (characters + their background boxes).
    Returns an RGBA numpy array (transparent background, opaque text).
    """
    doc = fitz.open(pdf_path)
    full = render_to_array(doc, dpi)

    if full.shape != no_text_arr.shape:
        raise ValueError(
            f"Shape mismatch between full ({full.shape}) and "
            f"no-text ({no_text_arr.shape}) renders. "
            "Ensure both use the same DPI."
        )

    mask = np.any(full != no_text_arr, axis=2)
    if verbose:
        pct = mask.sum() / mask.size * 100
        print(f"  Text pixels: {mask.sum():,}  ({pct:.2f}% of image)")

    result = np.zeros((full.shape[0], full.shape[1], 4), dtype=np.uint8)
    result[mask, :3] = full[mask]
    result[mask, 3] = 255
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog="map_extract",
        description=(
            "Extract text-free and/or text-only images from a CAD/map PDF.\n\n"
            "The PDF must be on the first page. Both outputs share the same DPI "
            "so they can be overlaid pixel-perfectly."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Save both outputs into ./output/\n"
            "  python map_extract.py map.pdf --both ./output/\n\n"
            "  # Text-free only at 72 DPI (smaller file, faster)\n"
            "  python map_extract.py map.pdf --no-text clean.png --dpi 72\n\n"
            "  # Text-only transparent overlay, verbose\n"
            "  python map_extract.py map.pdf --text-only labels.png -v\n\n"
            "  # Both, verbose, 100 DPI\n"
            "  python map_extract.py map.pdf --both . --dpi 100 -v"
        ),
    )
    parser.add_argument("pdf", help="Input PDF file path")
    parser.add_argument(
        "--no-text", metavar="PATH",
        help="Output path for the text-free PNG (RGB)"
    )
    parser.add_argument(
        "--text-only", metavar="PATH",
        help="Output path for the text-only transparent PNG (RGBA)"
    )
    parser.add_argument(
        "--both", metavar="DIR",
        help=(
            "Save both images to this directory. "
            "Auto-names them <stem>_no_text.png and <stem>_text_only.png"
        ),
    )
    parser.add_argument(
        "--dpi", type=int, default=150,
        help="Render resolution in DPI (default: 150). Use 72 for a quick preview."
    )
    parser.add_argument(
        "--line-scale", type=float, default=1.0, metavar="FACTOR",
        help="Multiply all line widths by this factor before rendering (e.g. 2.0 doubles thickness). "
             "Hairlines (width=0) are raised to 0.5pt × factor. Default: 1.0 (no change)."
    )
    parser.add_argument(
        "--list-layers", action="store_true",
        help="Print all OCG layers in the PDF and exit (useful for inspection)"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Print progress details"
    )

    args = parser.parse_args()

    if not os.path.isfile(args.pdf):
        print(f"Error: file not found: {args.pdf}", file=sys.stderr)
        sys.exit(1)

    # --list-layers: inspect mode
    if args.list_layers:
        doc = fitz.open(args.pdf)
        ocgs = doc.get_ocgs()
        if not ocgs:
            print("No OCG layers found in this PDF.")
        else:
            print(f"{'ID':>5}  {'Name'}")
            print("-" * 60)
            for xref, info in sorted(ocgs.items()):
                marker = "  [TEXT]" if any(
                    k in info["name"].lower() for k in TEXT_LAYER_KEYWORDS
                ) else ""
                print(f"{xref:>5}  {info['name']}{marker}")
        sys.exit(0)

    if not args.no_text and not args.text_only and not args.both:
        parser.error("Specify at least one of: --no-text, --text-only, or --both")

    # Resolve output paths
    stem = os.path.splitext(os.path.basename(args.pdf))[0]
    if args.both:
        os.makedirs(args.both, exist_ok=True)
        no_text_path  = os.path.join(args.both, f"{stem}_no_text.png")
        text_only_path = os.path.join(args.both, f"{stem}_text_only.png")
        do_no_text   = True
        do_text_only = True
    else:
        no_text_path   = args.no_text
        text_only_path = args.text_only
        do_no_text     = bool(args.no_text)
        do_text_only   = bool(args.text_only)

    # --- Step 1: no-text render (needed for both outputs) ---
    if verbose := args.verbose:
        step = 1
        total_steps = 1 + (1 if do_text_only else 0)
        print(f"[{step}/{total_steps}] Building text-free image  (DPI={args.dpi}) ...")

    no_text_arr = build_no_text(args.pdf, args.dpi, args.verbose, line_scale=args.line_scale)

    if do_no_text:
        Image.fromarray(no_text_arr).save(no_text_path)
        size_kb = os.path.getsize(no_text_path) // 1024
        print(f"  -> {no_text_path}  ({size_kb} KB)")

    # --- Step 2: text-only diff ---
    if do_text_only:
        if args.verbose:
            print(f"[2/{total_steps}] Building text-only image ...")
        text_arr = build_text_only(args.pdf, no_text_arr, args.dpi, args.verbose)
        Image.fromarray(text_arr).save(text_only_path)
        size_kb = os.path.getsize(text_only_path) // 1024
        print(f"  -> {text_only_path}  ({size_kb} KB)")

    print("Done.")


if __name__ == "__main__":
    main()
