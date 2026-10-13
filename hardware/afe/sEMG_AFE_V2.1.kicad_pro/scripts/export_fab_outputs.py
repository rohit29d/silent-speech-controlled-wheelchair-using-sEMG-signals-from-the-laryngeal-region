#!/usr/bin/env python3
"""
Automated KiCad Project Fabrication Outputs Exporter

Exports schematic PDF/SVG, BOM (CSV + Excel), Gerbers, drill files,
assembly PDFs, Pick & Place CSV, 3D renders, and interactive BOM.
Generates a README.md summarizing all outputs.

Usage:
    python export_fab_outputs.py
    (Run in the directory containing the .kicad_pro file)

Requirements:
    - kicad-cli installed and in PATH (KiCad 6+)
    - Python 3.x
    - pandas, openpyxl libraries
    - Optional: generate_interactive_bom (InteractiveHtmlBom plugin)
    - Optional: pcbnew Python module for zone refilling
"""

__version__ = "2.0.0"

import os
import re
import sys
import time
import shutil
import logging
import argparse
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

# -------------------- Logging Setup --------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


# -------------------- Dependency Checks --------------------
def check_dependencies():
    """Check for required dependencies and exit if not found."""
    logger.info(f"Script version: {__version__}")

    try:
        result = subprocess.run(
            ["kicad-cli", "--version"],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5
        )
        logger.info(f"KiCad CLI version: {result.stdout.decode().strip()}")
    except FileNotFoundError:
        logger.error("❌ kicad-cli is not installed or not in PATH.")
        logger.error("Please install KiCad 6.0 or newer.")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        logger.error("❌ kicad-cli timed out. Please check your KiCad installation.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Error checking kicad-cli: {e}")
        sys.exit(1)

    try:
        import pandas
        logger.info(f"pandas version: {pandas.__version__}")
    except ImportError:
        logger.error("❌ pandas is not installed. Run: pip install pandas openpyxl")
        sys.exit(1)


# -------------------- Utility Functions --------------------
def get_project_name(project_dir=None):
    """Search for a .kicad_pro file and return the project name."""
    try:
        if project_dir is None:
            project_dir = os.getcwd()
        if not os.path.isdir(project_dir):
            logger.error(f"Directory does not exist: {project_dir}")
            return None
        for fname in os.listdir(project_dir):
            if fname.endswith(".kicad_pro"):
                return os.path.splitext(fname)[0]
        return None
    except PermissionError:
        logger.error(f"Permission denied accessing directory: {project_dir}")
        return None
    except Exception as e:
        logger.error(f"Error reading project directory: {e}")
        return None


PROJECT_NAME = get_project_name()
if PROJECT_NAME is None:
    print("❌ No .kicad_pro file found in the current directory.")
    sys.exit(1)

PROJECT_DIR = os.getcwd()
OUTPUT_DIR = os.path.join(PROJECT_DIR, "output")


def ensure_dir(directory):
    """Create directory if it doesn't exist."""
    try:
        os.makedirs(directory, exist_ok=True)
        return True
    except PermissionError:
        logger.error(f"❌ Permission denied creating directory: {directory}")
        return False
    except Exception as e:
        logger.error(f"❌ Error creating directory {directory}: {e}")
        return False


def run_command(command, output_file=None):
    """Run a subprocess command with error handling and optional output file check."""
    logger.info(f"Running: {' '.join(command) if isinstance(command, list) else command}")
    try:
        result = subprocess.run(
            command,
            check=True,
            shell=isinstance(command, str),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=300
        )
        if output_file and not os.path.exists(output_file):
            logger.error(f"❌ Expected output file not found: {output_file}")
            return False
        logger.info("Done")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Command failed with exit code {e.returncode}")
        if e.stderr:
            logger.error(f"Error output: {e.stderr.decode().strip()}")
        return False
    except subprocess.TimeoutExpired:
        logger.error("❌ Command timed out after 300 seconds")
        return False
    except FileNotFoundError:
        logger.error(f"❌ Command not found: {command[0] if isinstance(command, list) else command}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error running command: {e}")
        return False


# -------------------- Zone Refill --------------------
def refill_zones(pcb_file):
    """Refill all copper zones using the pcbnew Python API (if available)."""
    logger.info("Refilling zones in PCB...")

    if not os.path.exists(pcb_file):
        logger.error(f"❌ PCB file not found: {pcb_file}")
        return False

    try:
        import pcbnew
    except ImportError:
        logger.warning("⚠️  pcbnew module not available — skipping zone refill.")
        logger.warning("   Fill zones manually in KiCad (press 'B') before running this script")
        logger.warning("   to avoid DRC shorts/clearance violations on copper pours.")
        return True  # non-fatal; DRC will surface any issues

    try:
        board = pcbnew.LoadBoard(pcb_file)
        zones = board.Zones()
        if not zones or len(zones) == 0:
            logger.info("No zones found in PCB — skipping refill.")
            return True
        logger.info(f"Found {len(zones)} zone(s) — refilling...")
        filler = pcbnew.ZONE_FILLER(board)
        filler.Fill(zones)
        board.Save(pcb_file)
        logger.info("✅ Zones refilled and PCB saved.")
        return True
    except PermissionError:
        logger.error(f"❌ Permission denied saving PCB file: {pcb_file}")
        return False
    except Exception as e:
        logger.error(f"❌ Failed to refill zones: {e}")
        logger.error("   Please manually fill zones in KiCad ('B' key) and re-run.")
        return False


# -------------------- ERC / DRC --------------------
def run_erc(sch_file, output_dir):
    """Run Electrical Rules Check; fail on real (non-excluded) errors."""
    out = os.path.join(output_dir, "erc_report.txt")
    if not os.path.exists(sch_file):
        logger.error(f"❌ Schematic file not found: {sch_file}")
        return False

    cmd = ["kicad-cli", "sch", "erc", sch_file, "--output", out]
    if not run_command(cmd, out):
        return False

    try:
        with open(out, "r", encoding="utf-8") as f:
            content = f.read()
        for line in content.splitlines():
            if "** Found" in line and "ERC violations **" in line:
                match = re.search(r"Found (\d+) ERC violations", line)
                if match and int(match.group(1)) > 0:
                    has_errors = any(
                        "; error" in l and "(excluded)" not in l
                        for l in content.splitlines()
                    )
                    if has_errors:
                        logger.error(f"ERC found {match.group(1)} violation(s) with errors. See: {out}")
                        return False
    except IOError as e:
        logger.error(f"❌ Cannot read ERC report: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Error parsing ERC report: {e}")
        return False

    return True


def run_drc(pcb_file, output_dir):
    """Run DRC with detailed error reporting, category breakdown, and exception handling."""
    out = os.path.join(output_dir, "drc_report.txt")
    if not os.path.exists(pcb_file):
        logger.error(f"❌ PCB file not found: {pcb_file}")
        return False

    cmd = ["kicad-cli", "pcb", "drc", pcb_file, "--output", out, "--severity-all"]
    success = run_command(cmd, out)
    if not success:
        return False

    try:
        if os.path.exists(out):
            with open(out, "r", encoding="utf-8") as f:
                content = f.read()

            for line in content.splitlines():
                if "** Found" in line and "DRC violations **" in line:
                    from collections import defaultdict
                    match = re.search(r"Found (\d+) DRC violations", line)
                    if match and int(match.group(1)) > 0:
                        lines = content.splitlines()
                        error_types = defaultdict(lambda: {"excluded": 0, "non_excluded": 0})
                        warning_types = defaultdict(lambda: {"excluded": 0, "non_excluded": 0})
                        current_type = None

                        for l in lines:
                            type_match = re.match(r"^\[([^\]]+)\]:", l)
                            if type_match:
                                current_type = type_match.group(1)
                            elif current_type and "; error" in l:
                                key = "excluded" if "(excluded)" in l else "non_excluded"
                                error_types[current_type][key] += 1
                                current_type = None
                            elif current_type and "; warning" in l:
                                key = "excluded" if "(excluded)" in l else "non_excluded"
                                warning_types[current_type][key] += 1
                                current_type = None

                        total_errors_excluded = sum(v["excluded"] for v in error_types.values())
                        total_errors_non_excluded = sum(v["non_excluded"] for v in error_types.values())
                        total_warnings_excluded = sum(v["excluded"] for v in warning_types.values())
                        total_warnings_non_excluded = sum(v["non_excluded"] for v in warning_types.values())

                        logger.info(f"DRC Summary: {match.group(1)} total violations")
                        logger.info(f"  Errors: {total_errors_non_excluded} non-excluded, {total_errors_excluded} excluded")
                        logger.info(f"  Warnings: {total_warnings_non_excluded} non-excluded, {total_warnings_excluded} excluded")

                        if error_types:
                            logger.info("Error breakdown by type:")
                            for error_type in sorted(error_types.keys()):
                                counts = error_types[error_type]
                                logger.info(f"  [{error_type}]: {counts['non_excluded']} non-excluded, {counts['excluded']} excluded")

                        if warning_types:
                            logger.info("Warning breakdown by type:")
                            for warning_type in sorted(warning_types.keys()):
                                counts = warning_types[warning_type]
                                logger.info(f"  [{warning_type}]: {counts['non_excluded']} non-excluded, {counts['excluded']} excluded")

                        if total_errors_non_excluded > 0:
                            logger.error(f"DRC found {total_errors_non_excluded} non-excluded error(s). See: {out}")
                            return False
    except IOError as e:
        logger.error(f"❌ Cannot read DRC report: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Error parsing DRC report: {e}")
        logger.warning("Continuing but DRC validation may be incomplete.")
        return True

    return success



# -------------------- Export Functions --------------------
def generate_schematic_pdf(sch_file, output_dir, project_name):
    out = os.path.join(output_dir, f"{project_name}_schematic.pdf")
    cmd = ["kicad-cli", "sch", "export", "pdf", sch_file, "--output", out]
    return run_command(cmd, out)


def export_schematic_svg(sch_file, output_dir, project_name):
    out = os.path.join(output_dir, f"{project_name}_schematic.svg")
    cmd = ["kicad-cli", "sch", "export", "svg", sch_file, "--output", out]
    return run_command(cmd, out)


def export_bom(sch_file, output_dir, project_name):
    """Export BOM as CSV then convert to Excel."""
    csv_path  = os.path.join(output_dir, f"{project_name}_BOM.csv")
    xlsx_path = os.path.join(output_dir, f"{project_name}_BOM.xlsx")

    cmd = [
        "kicad-cli", "sch", "export", "bom", sch_file,
        "--group-by", "Value,Footprint,${DNP}",
        "--ref-range-delimiter", "",
        "--fields", "${ITEM_NUMBER},Reference,Value,Footprint,Description,${QUANTITY},${DNP},MPN,SKU,Link",
        "--output", csv_path
    ]
    success = run_command(cmd, csv_path)
    if success and os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path)
            df.to_excel(xlsx_path, index=False)
            logger.info(f"Converted CSV BOM to Excel: {xlsx_path}")
            return True
        except pd.errors.EmptyDataError:
            logger.error(f"❌ BOM CSV is empty: {csv_path}")
        except pd.errors.ParserError as e:
            logger.error(f"❌ Error parsing BOM CSV: {e}")
        except PermissionError:
            logger.error(f"❌ Permission denied writing Excel file: {xlsx_path}")
        except Exception as e:
            logger.error(f"❌ Error converting BOM to Excel: {e}")
        return False
    logger.error(f"❌ BOM CSV not found for conversion: {csv_path}")
    return False


def export_gerbers(pcb_file, output_dir, project_name):
    gerbers_dir = os.path.join(output_dir, "Gerbers")
    ensure_dir(gerbers_dir)
    cmd = [
        "kicad-cli", "pcb", "export", "gerbers", pcb_file,
        "--board-plot-params",
        "--layers", "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Mask,B.Mask,F.Paste,B.Paste,"
                    "F.Silkscreen,B.Silkscreen,Edge.Cuts",
        "--output", gerbers_dir
    ]
    return run_command(cmd)


def export_drill(pcb_file, output_dir):
    gerbers_dir = os.path.join(output_dir, "Gerbers")
    ensure_dir(gerbers_dir)
    cmd = ["kicad-cli", "pcb", "export", "drill", pcb_file, "--output", gerbers_dir]
    return run_command(cmd)


def export_position(pcb_file, output_dir, project_name):
    out = os.path.join(output_dir, "Gerbers", f"{project_name}-all-pos.csv")
    cmd = [
        "kicad-cli", "pcb", "export", "pos", pcb_file,
        "--format", "csv", "--units", "mm", "--exclude-dnp",
        "--output", out
    ]
    return run_command(cmd, out)


def export_top_assembly(pcb_file, output_dir, project_name):
    out = os.path.join(output_dir, f"{project_name}_Top_Assembly.pdf")
    cmd = [
        "kicad-cli", "pcb", "export", "pdf", pcb_file,
        "--layers", "F.Mask,F.Silkscreen,Edge.Cuts,User.Drawings",
        "--black-and-white", "--output", out
    ]
    return run_command(cmd, out)


def export_bottom_assembly(pcb_file, output_dir, project_name):
    out = os.path.join(output_dir, f"{project_name}_Bottom_Assembly.pdf")
    cmd = [
        "kicad-cli", "pcb", "export", "pdf", pcb_file,
        "--layers", "B.Mask,B.Silkscreen,Edge.Cuts",
        "--black-and-white", "--mirror", "--output", out
    ]
    return run_command(cmd, out)


def take_3d_screenshots(pcb_file, output_dir, project_name):
    top   = os.path.join(output_dir, f"{project_name}_3D_top.png")
    bot   = os.path.join(output_dir, f"{project_name}_3D_bottom.png")
    persp = os.path.join(output_dir, f"{project_name}_3D_perspective.png")
    cmds = [
        (["kicad-cli", "pcb", "render", pcb_file, "--side", "top",    "--output", top],   top),
        (["kicad-cli", "pcb", "render", pcb_file, "--side", "bottom", "--output", bot],   bot),
        (["kicad-cli", "pcb", "render", pcb_file, "--side", "top",
          "--perspective", "--rotate", "315,0,0",              "--output", persp], persp),
    ]
    return all(run_command(cmd, outfile) for cmd, outfile in cmds)


# -------------------- Interactive BOM --------------------
def find_interactive_bom_executable():
    """Locate generate_interactive_bom on PATH or common venv locations."""
    env_override = os.environ.get("INTERACTIVE_BOM_EXE")
    if env_override and os.path.isfile(env_override) and os.access(env_override, os.X_OK):
        return env_override
    exe = shutil.which("generate_interactive_bom")
    if exe:
        return exe
    for candidate in [
        os.path.join(os.path.dirname(sys.executable), "generate_interactive_bom"),
        os.path.expanduser("~/.venvs/kicad/bin/generate_interactive_bom"),
    ]:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def generate_interactive_bom(pcb_file, output_dir):
    """Generate interactive HTML BOM (requires InteractiveHtmlBom plugin)."""
    exe = find_interactive_bom_executable()
    if not exe:
        logger.warning("⚠️  generate_interactive_bom not found — skipping interactive BOM.")
        return False
    ibom_dir = os.path.join(output_dir, "ibom")
    ensure_dir(ibom_dir)
    cmd = [exe, pcb_file, "--no-browser", "--highlight-pin1", "--dest-dir", ibom_dir]
    result = run_command(cmd)
    if result:
        logger.info(f"✅ Interactive BOM generated at {ibom_dir}")
    return result


# -------------------- README Generation --------------------
def write_readme(project_dir, output_dir, project_name):
    """Write a README.md summarising all generated outputs."""
    readme_path = os.path.join(project_dir, "README.md")

    def rel(path):
        return os.path.relpath(path, project_dir)

    content = f"""# {project_name}

> Generated with export_fab_outputs.py v{__version__}

## 🚀 How to Use the Automation Script

### 🔧 Command Line (Terminal)

Run the following command **from the project directory** (where `.kicad_pro` is located):

```bash
make
```

To generate a zip of Gerbers for fabrication:
```bash
make release
```

Or run the script directly:
```bash
python3 scripts/export_fab_outputs.py
```

---

### 3D Views
#### Top View
![]({rel(os.path.join(output_dir, project_name + '_3D_top.png'))})
#### Bottom View
![]({rel(os.path.join(output_dir, project_name + '_3D_bottom.png'))})
#### Perspective View
![]({rel(os.path.join(output_dir, project_name + '_3D_perspective.png'))})

---

### Schematic
[{project_name}_schematic.pdf]({rel(os.path.join(output_dir, project_name + '_schematic.pdf'))})

### BOM
[{project_name}_BOM.xlsx]({rel(os.path.join(output_dir, project_name + '_BOM.xlsx'))})

### Top Assembly
[{project_name}_Top_Assembly.pdf]({rel(os.path.join(output_dir, project_name + '_Top_Assembly.pdf'))})

### Bottom Assembly
[{project_name}_Bottom_Assembly.pdf]({rel(os.path.join(output_dir, project_name + '_Bottom_Assembly.pdf'))})

### Gerbers & Drill Files
[Gerbers/]({rel(os.path.join(output_dir, 'Gerbers'))})

### Pick & Place
[{project_name}-all-pos.csv]({rel(os.path.join(output_dir, 'Gerbers', project_name + '-all-pos.csv'))})

### Interactive BOM
Download and open [ibom.html]({rel(os.path.join(output_dir, 'ibom', 'ibom.html'))}) in browser
"""

    try:
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"README.md written to {readme_path}")
        return True
    except PermissionError:
        logger.error(f"❌ Permission denied writing README: {readme_path}")
        return False
    except Exception as e:
        logger.error(f"❌ Error writing README: {e}")
        return False


# -------------------- Main Orchestration --------------------
def main():
    parser = argparse.ArgumentParser(
        description="Automated KiCad Project Fabrication Outputs Exporter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("--skip-erc", action="store_true", help="Skip ERC schematic verification")
    parser.add_argument("--skip-drc", action="store_true", help="Skip DRC PCB verification")
    parser.add_argument("--workers", "-w", type=int, default=4, help="Parallel worker threads (default: 4)")
    args = parser.parse_args()

    start_time = time.time()
    logger.info(f"Starting export for project: {PROJECT_NAME}")
    check_dependencies()
    ensure_dir(OUTPUT_DIR)

    sch_file = os.path.join(PROJECT_DIR, f"{PROJECT_NAME}.kicad_sch")
    pcb_file = os.path.join(PROJECT_DIR, f"{PROJECT_NAME}.kicad_pcb")

    if not os.path.isfile(sch_file):
        logger.error(f"Schematic file not found: {sch_file}")
        sys.exit(1)
    if not os.path.isfile(pcb_file):
        logger.error(f"PCB file not found: {pcb_file}")
        sys.exit(1)

    # --- Sequential: checks must pass before generating outputs ---
    if not args.skip_erc:
        logger.info("Running ERC (Electrical Rules Check)...")
        if not run_erc(sch_file, OUTPUT_DIR):
            logger.error("❌ ERC failed. Fix schematic errors before generating outputs.")
            sys.exit(1)
        logger.info("✅ ERC passed")
    else:
        logger.warning("⚠️  Skipping ERC as requested by --skip-erc")

    if not refill_zones(pcb_file):
        logger.error("❌ Zone refill failed. Cannot proceed with DRC.")
        sys.exit(1)

    if not args.skip_drc:
        logger.info("Running DRC (Design Rules Check)...")
        if not run_drc(pcb_file, OUTPUT_DIR):
            logger.error("❌ DRC failed. Fix PCB errors before generating outputs.")
            sys.exit(1)
        logger.info("✅ DRC passed")
    else:
        logger.warning("⚠️  Skipping DRC as requested by --skip-drc")

    # --- Parallel: all export tasks ---
    tasks = [
        (generate_schematic_pdf,   (sch_file, OUTPUT_DIR, PROJECT_NAME)),
        (export_schematic_svg,     (sch_file, OUTPUT_DIR, PROJECT_NAME)),
        (export_bom,               (sch_file, OUTPUT_DIR, PROJECT_NAME)),
        (export_gerbers,           (pcb_file, OUTPUT_DIR, PROJECT_NAME)),
        (export_drill,             (pcb_file, OUTPUT_DIR)),
        (export_position,          (pcb_file, OUTPUT_DIR, PROJECT_NAME)),
        (export_top_assembly,      (pcb_file, OUTPUT_DIR, PROJECT_NAME)),
        (export_bottom_assembly,   (pcb_file, OUTPUT_DIR, PROJECT_NAME)),
        (take_3d_screenshots,      (pcb_file, OUTPUT_DIR, PROJECT_NAME)),
        (generate_interactive_bom, (pcb_file, OUTPUT_DIR)),
    ]

    failed_tasks = []
    try:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            future_to_task = {
                executor.submit(func, *params): func.__name__
                for func, params in tasks
            }
            for future in as_completed(future_to_task):
                name = future_to_task[future]
                try:
                    if future.result():
                        logger.info(f"{name}: ✅ Success")
                    else:
                        logger.error(f"{name}: ❌ Failed")
                        failed_tasks.append(name)
                except Exception as exc:
                    logger.error(f"{name} generated an exception: {exc}")
                    failed_tasks.append(name)
    except Exception as e:
        logger.error(f"❌ Error during parallel task execution: {e}")

    if failed_tasks:
        logger.warning(f"⚠️  {len(failed_tasks)} task(s) failed: {', '.join(failed_tasks)}")

    try:
        if not write_readme(PROJECT_DIR, OUTPUT_DIR, PROJECT_NAME):
            logger.warning("⚠️  README generation failed, continuing...")
    except Exception as e:
        logger.warning(f"⚠️  README generation exception: {e}")

    elapsed = time.time() - start_time
    logger.info(f"✅ All tasks completed in {elapsed:.2f} seconds.")

    if failed_tasks:
        logger.warning("Some tasks failed — check logs above for details.")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.error("\n❌ Script interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"❌ Unexpected fatal error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)
