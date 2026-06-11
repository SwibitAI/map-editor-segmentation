#!/usr/bin/env python3
"""
pdf_lines.py — Extract all vector line segments from a map PDF.
Outputs a JSON file ready for the line-connect.html viewer.

Usage:
    python pdf_lines.py input.pdf output.json
    python pdf_lines.py input.pdf output.json --layers "0,Home (1),0_UNIT-1"
    python pdf_lines.py input.pdf output.json --all-layers
    python pdf_lines.py input.pdf          # prints layer list and exits
"""

import argparse, json, math, sys
import fitz


def list_layers(doc):
    page = doc[0]
    drawings = page.get_drawings()
    import collections
    by_layer = collections.Counter(d.get("layer", "(none)") for d in drawings)
    stroke_by_layer = collections.Counter(
        d.get("layer", "(none)") for d in drawings if d["type"] in ("s", "fs")
    )
    print(f"{'Layer name':<40} {'total':>7}  {'strokes':>8}")
    print("-" * 60)
    for layer, count in by_layer.most_common():
        print(f"{layer:<40} {count:>7}  {stroke_by_layer.get(layer, 0):>8}")


def extract_segments(doc, layer_filter=None):
    page = doc[0]
    W, H = page.rect.width, page.rect.height
    drawings = page.get_drawings()

    segments = []
    texts = []

    for d in drawings:
        layer = d.get("layer", "")
        if layer_filter is not None and layer not in layer_filter:
            continue
        if d["type"] not in ("s", "fs"):
            continue

        color = d.get("color")
        col_hex = (
            "#{:02x}{:02x}{:02x}".format(
                int(color[0] * 255), int(color[1] * 255), int(color[2] * 255)
            )
            if color
            else "#000000"
        )
        width = d.get("width") or 0.0

        for op in d["items"]:
            kind = op[0]
            if kind == "l":
                segments.append(
                    {
                        "a": [round(op[1].x, 3), round(op[1].y, 3)],
                        "b": [round(op[2].x, 3), round(op[2].y, 3)],
                        "layer": layer,
                        "color": col_hex,
                        "width": round(width, 3),
                    }
                )
            elif kind == "re":
                r = op[1]
                corners = [
                    [r.x0, r.y0],
                    [r.x1, r.y0],
                    [r.x1, r.y1],
                    [r.x0, r.y1],
                ]
                for i in range(4):
                    segments.append(
                        {
                            "a": [round(corners[i][0], 3), round(corners[i][1], 3)],
                            "b": [
                                round(corners[(i + 1) % 4][0], 3),
                                round(corners[(i + 1) % 4][1], 3),
                            ],
                            "layer": layer,
                            "color": col_hex,
                            "width": round(width, 3),
                        }
                    )
            elif kind == "qu":
                q = op[1]
                corners = [
                    [q.ul.x, q.ul.y],
                    [q.ur.x, q.ur.y],
                    [q.lr.x, q.lr.y],
                    [q.ll.x, q.ll.y],
                ]
                for i in range(4):
                    segments.append(
                        {
                            "a": [round(corners[i][0], 3), round(corners[i][1], 3)],
                            "b": [
                                round(corners[(i + 1) % 4][0], 3),
                                round(corners[(i + 1) % 4][1], 3),
                            ],
                            "layer": layer,
                            "color": col_hex,
                            "width": round(width, 3),
                        }
                    )
            elif kind == "c":
                # Bezier: approximate with a few line segments
                p0, p1, p2, p3 = op[1], op[2], op[3], op[4]
                prev = [p0.x, p0.y]
                steps = 8
                for i in range(1, steps + 1):
                    t = i / steps
                    mt = 1 - t
                    x = mt**3*p0.x + 3*mt**2*t*p1.x + 3*mt*t**2*p2.x + t**3*p3.x
                    y = mt**3*p0.y + 3*mt**2*t*p1.y + 3*mt*t**2*p2.y + t**3*p3.y
                    segments.append(
                        {
                            "a": [round(prev[0], 3), round(prev[1], 3)],
                            "b": [round(x, 3), round(y, 3)],
                            "layer": layer,
                            "color": col_hex,
                            "width": round(width, 3),
                        }
                    )
                    prev = [x, y]

    # Extract text
    page_dict = page.get_text("dict")
    for block in page_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                txt = span["text"].strip()
                if not txt:
                    continue
                bbox = span["bbox"]
                texts.append(
                    {
                        "text": txt,
                        "x": round((bbox[0] + bbox[2]) / 2, 3),
                        "y": round((bbox[1] + bbox[3]) / 2, 3),
                        "size": round(span["size"], 2),
                        "color": "#{:06x}".format(span.get("color", 0)),
                    }
                )

    all_layers = sorted(set(s["layer"] for s in segments))
    return {
        "page": {"width": round(W, 2), "height": round(H, 2)},
        "layers": all_layers,
        "segments": segments,
        "texts": texts,
    }


def main():
    parser = argparse.ArgumentParser(description="Extract vector lines from a map PDF")
    parser.add_argument("pdf", help="Input PDF file")
    parser.add_argument("output", nargs="?", help="Output JSON file (omit to list layers)")
    parser.add_argument(
        "--layers",
        help='Comma-separated layer names to include, e.g. "0,Home (1),0_UNIT-1"',
    )
    parser.add_argument(
        "--all-layers", action="store_true", help="Include all layers (default: all)"
    )
    args = parser.parse_args()

    doc = fitz.open(args.pdf)

    if not args.output:
        list_layers(doc)
        return

    layer_filter = None
    if args.layers:
        layer_filter = set(l.strip() for l in args.layers.split(","))
        print(f"Filtering to layers: {layer_filter}")

    print(f"Extracting from {args.pdf} ...")
    data = extract_segments(doc, layer_filter)
    print(f"  {len(data['segments'])} segments across {len(data['layers'])} layers")
    print(f"  {len(data['texts'])} text spans")

    with open(args.output, "w") as f:
        json.dump(data, f, separators=(",", ":"))

    import os
    size_kb = os.path.getsize(args.output) // 1024
    print(f"  -> {args.output}  ({size_kb} KB)")


if __name__ == "__main__":
    main()
