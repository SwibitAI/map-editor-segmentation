# Map Segmentation Tool

Extracts vector line data from CAD/map PDFs, connects fragmented segments into clean polylines and closed polygon outlines using graph tracing, and exports the results as GeoJSON.

---

## Files

| File | Role |
|---|---|
| `pdf_lines.py` | Extracts all stroke paths from a PDF as line segments → JSON |
| `line-connect.html` | Interactive viewer — snap, dedup, connect, detect polygons, export |

---

## Requirements

```bash
pip install PyMuPDF
python3 -m http.server 8080   # to serve the HTML tool
```

---

## Usage

### Step 1 — Extract lines from PDF

```bash
python pdf_lines.py input.pdf output/lines_data.json

# Extract specific layers only (recommended for cleaner results)
python pdf_lines.py input.pdf output/lines_data.json --layers "Home (1),0_UNIT-1"

# List all layers in the PDF first
python pdf_lines.py input.pdf
```

Output JSON:
```json
{
  "page": { "width": 1191.0, "height": 842.0 },
  "layers": ["0", "Home (1)", "0_UNIT-1", ...],
  "segments": [
    { "a": [x1, y1], "b": [x2, y2], "layer": "Home (1)", "color": "#000000", "width": 0.0 }
  ],
  "texts": [
    { "text": "B12", "x": 543.2, "y": 210.5, "size": 8.0, "color": "#000000" }
  ]
}
```

### Step 2 — Open the viewer

```bash
python3 -m http.server 8080
# open http://localhost:8080/line-connect.html
# auto-loads output/lines_data.json if present
```

---

## Segmentation Algorithm

1. **Snap** — round all endpoints to a configurable grid (closes micro-gaps from CAD export)
2. **Deduplicate** — remove segments with identical snapped endpoints
3. **Adjacency graph** — nodes = snapped endpoints, edges = segments
4. **Trace chains** — walk through degree-2 nodes, stop at junctions (degree ≠ 2)
5. **Detect polygons** — closed chains where `start ≈ end` (within `snapTol × 3`)
6. **Collinear merge** (optional) — merge overlapping segments on the same infinite line into one

---

## Controls

| Control | Effect |
|---|---|
| **Snap** slider (0.1–10 pt) | Grid cell size — larger bridges bigger gaps between segments |
| **Min length** slider | Discard segments shorter than this (removes noise) |
| **Collinear merge** checkbox | Merge overlapping collinear segments |
| **Layer toggles** | Show/hide individual PDF layers |
| **Raw** mode | All segments color-coded by layer |
| **Connected** mode | Traced polylines highlighted, polygon fills shown |
| **Polygons** mode | Closed polygons only |
| **Text** toggle | Show/hide text labels extracted from PDF |
| **Export GeoJSON** | Download all detected polygons and polylines |

---

## Example Results

Running on a CAD land parcel map (A4 landscape, 22 layers) at snap = 1 pt:

| Stage | Count |
|---|---|
| Raw segments | 98,215 |
| After snap + dedup | 29,203 |
| Traced polylines | 22,297 |
| Closed polygons | 337 |

For block-boundary polygons only, disable all layers except the block outline layer before exporting.

---

## Notes

- **Coordinates** are in PDF points (origin top-left, Y grows downward)
- **Shared-edge layouts** (parcel grids): the tracer produces outer block boundaries, not individual cells, because shared-edge corners are degree-3+ nodes. Individual cell extraction requires planar face detection (DCEL) — not yet implemented.
- Works in Chrome, Firefox, Edge, Safari — no build step, no dependencies
