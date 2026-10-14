# KiCad Automation Scripts

> Generated with script suite v1.0.0

## 🚀 Overview

Two Python scripts to fully automate KiCad fabrication output generation and design verification — no GUI required.

**Compatible with KiCad 6, 7, 8, and 9.x** via `kicad-cli`. No `pcbnew` Python bindings required (zone refill is attempted if available, gracefully skipped if not).

---

## 📁 Scripts

| Script | Purpose |
|---|---|
| `export_fab_outputs.py` | ERC → DRC → parallel export of all fab deliverables + README |
| `run_checks.py` | Standalone ERC + DRC runner with detailed violation breakdown |

---

## ⚙️ Requirements

```
Python 3.x
KiCad 6.0+ (kicad-cli must be on PATH)
pip install pandas openpyxl
```

Optional:
- `pcbnew` Python module — for automatic zone refilling before DRC (bundled with KiCad)
- `generate_interactive_bom` — for interactive HTML BOM ([InteractiveHtmlBom plugin](https://github.com/openscopeproject/InteractiveHtmlBom))

---

## 🔧 Quick Start

Place both scripts in a `scripts/` folder inside your KiCad project, then run from the **project root** (the directory containing your `.kicad_pro` file).

### Command 1 — Export All Fabrication Outputs

```bash
python3 scripts/export_fab_outputs.py
```

This will:
1. Run **ERC** — exits immediately if real schematic errors are found
2. **Refill zones** (if pcbnew is available)
3. Run **DRC** — exits immediately if real PCB errors are found
4. Export all outputs **in parallel** (4 workers)
5. Write a `README.md` to the project root with links to all outputs

**Output structure:**
```
output/
├── erc_report.txt
├── drc_report.txt
├── <project>_schematic.pdf
├── <project>_schematic.svg
├── <project>_BOM.csv
├── <project>_BOM.xlsx
├── <project>_Top_Assembly.pdf
├── <project>_Bottom_Assembly.pdf
├── <project>_3D_top.png
├── <project>_3D_bottom.png
├── <project>_3D_perspective.png
├── Gerbers/
│   ├── <project>-F_Cu.gbr
│   ├── <project>-B_Cu.gbr
│   ├── <project>-F_Mask.gbr  ... (all layers)
│   ├── <project>-PTH.drl
│   ├── <project>-NPTH.drl
│   └── <project>-all-pos.csv
└── ibom/
    └── ibom.html
```

---

### Command 2 — Run Design Checks Only

```bash
python3 scripts/run_checks.py
```

Runs both ERC and DRC, prints a detailed breakdown of violations by type/severity, and exits `1` if any non-excluded errors are found — suitable for CI pipelines.

**Options:**

```bash
python3 scripts/run_checks.py --drc-only          # skip ERC
python3 scripts/run_checks.py --erc-only          # skip DRC
python3 scripts/run_checks.py --output reports/   # custom report directory
```

**Example output:**
```
2025-01-15 12:34:56 [INFO] ✅ ERC passed
2025-01-15 12:34:58 [INFO] DRC Summary: 0 error(s) | 2 warning(s) | 1 excluded error(s)
2025-01-15 12:34:58 [INFO] ✅ DRC passed
2025-01-15 12:34:58 [INFO] ✅ All 2 check(s) passed in 3.21 seconds.
```

---

## 🔁 Makefile Targets

The project includes an automated Makefile that manages virtual environments (`~/.venvs/kicad`) and package dependencies automatically:

| Target | Command | Description |
|---|---|---|
| `all` / `fab` | `make` or `make fab` | Runs ERC → DRC → parallel export of all fabrication outputs |
| `check` | `make check` | Runs standalone ERC and DRC verification |
| `buy` | `make buy` | Generates procurement BOM (`.csv` + `.xlsx`) & pick-and-place pos file in `pcbpower/` |
| `release` | `make release` | Runs export and packages Gerbers into a `_Gerbers.zip` archive |
| `clean` | `make clean` | Removes generated archives and temporary build files |

---

## 🤖 CI / GitHub Actions

```yaml
- name: Install Python dependencies
  run: pip install pandas openpyxl

- name: Run design checks
  run: python3 scripts/run_checks.py

- name: Export fabrication outputs
  run: python3 scripts/export_fab_outputs.py

- name: Upload Gerbers
  uses: actions/upload-artifact@v4
  with:
    name: gerbers
    path: output/Gerbers/
```

---

## 🛠️ Troubleshooting

**`❌ kicad-cli is not installed or not in PATH`**
Add KiCad's `bin/` folder to your PATH. On Linux: `/usr/bin/`, macOS: `/Applications/KiCad/KiCad.app/Contents/MacOS/`, Windows: `C:\Program Files\KiCad\9.0\bin\`.

**`❌ No .kicad_pro file found`**
Run the script from the project root directory, not from `scripts/`.

**`⚠️ pcbnew module not available — skipping zone refill`**
This is a warning, not an error. Either fill zones manually in KiCad (`B` key) before running, or run the scripts using KiCad's bundled Python: `/usr/bin/python3` (Linux) or the Python inside KiCad's install folder.

**BOM export fails on KiCad 6 / 7**
`kicad-cli sch export bom` was added in KiCad 8. For older versions, export BOM manually or use the [KiBoM plugin](https://github.com/SchrodingersGat/KiBoM).

**3D renders fail**
`kicad-cli pcb render` requires KiCad 7.0.8+. On headless CI servers it also requires a virtual display (e.g. `xvfb-run`).
