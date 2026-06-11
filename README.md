# Block Map Editor — Segmentation Tool

A single-file browser-based editor for digitizing and segmenting land parcel maps.
Draw polygon blocks over a background map image, divide them into columns and rows of units, and export the result as GeoJSON.

No build step, no dependencies, no server required — open `block-editor.html` directly in any modern browser.

---

## Demo

Load a map image, draw a block polygon, pick a baseline edge, and set the grid divisions. The editor segments the block into individually addressable units.

---

## Features

### Block drawing
- Click to place polygon vertices, double-click or click the first vertex to close
- Any convex or concave polygon shape

### Baseline-aligned grid
- Click any edge of the block to set it as the **baseline**
- Column dividers run perpendicular to the baseline
- Row dividers run parallel to the baseline
- Grid stays aligned even for rotated or irregular blocks

### Selection levels
Switch between four selection modes (keyboard: `1` `2` `3` `4`):

| Mode | What it selects | What you can do |
|---|---|---|
| **Block** | The whole polygon | Drag column dividers, move vertices |
| **Column** | One column strip | Drag row dividers, double-click to add/remove rows |
| **Row** | A full row band across all columns | Double-click to add/remove vertical sub-dividers |
| **Unit** | A single cell | Inspect, select for reference |

### Divider controls
- **Drag** any divider handle to resize — proportional redistribution keeps all adjacent cells equal
- **Lock icon** next to each handle — locked dividers are skipped during proportional drag
- **Double-click** a divider to remove it (merge two units)
- **Double-click** empty space (Column mode) to add a row divider at that position
- **Double-click** empty space (Row mode) to add a vertical sub-divider within that row band

### Per-column row counts
Each column can have a different number of rows — useful for blocks where one column has a different unit depth than its neighbours.

### GeoJSON export
Exports a `FeatureCollection` with:
- One `block` polygon feature per block
- One `unit` polygon feature per cell, with properties: `blockId`, `colIdx`, `rowIdx`, `subColIdx`, `unitNumber`

---

## Usage

```
open block-editor.html
```

1. Click **Load Image** → select your map PNG/JPG
2. Click **Draw Block** (or press `D`) → click vertices to outline a block → close the polygon
3. Click an edge to set it as the **baseline**
4. Enter column and row counts in the dialog → **OK**
5. Switch selection levels and adjust dividers as needed
6. Click **Export GeoJSON** to download

### Keyboard shortcuts

| Key | Action |
|---|---|
| `D` | Draw mode |
| `1` | Block selection |
| `2` | Column selection |
| `3` | Row selection |
| `4` | Unit selection |
| `Del` | Delete selected block or column |
| `Esc` | Cancel draw / deselect |
| Scroll | Zoom |
| Middle-click drag | Pan |

---

## GeoJSON output format

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": "block-1",
      "properties": { "type": "block", "id": 1 },
      "geometry": { "type": "Polygon", "coordinates": [[...]] }
    },
    {
      "type": "Feature",
      "id": "unit-1-1",
      "properties": {
        "type": "unit",
        "blockId": 1,
        "colIdx": 0,
        "rowIdx": 0,
        "subColIdx": 0,
        "unitNumber": 1
      },
      "geometry": { "type": "Polygon", "coordinates": [[...]] }
    }
  ]
}
```

---

## Browser compatibility

Chrome, Firefox, Edge, Safari — uses only Canvas 2D API and vanilla JS.
