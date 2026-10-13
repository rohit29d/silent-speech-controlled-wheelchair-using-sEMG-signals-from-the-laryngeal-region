#!/usr/bin/env python3
"""
KiCad Procurement BOM + Position File Exporter

Exports from a KiCad project:
  1. A procurement BOM (CSV + Excel) with these columns, in this order:
         Item, Reference, Value, Footprint, Description, Quantity, Sourced, Placed, MPN
  2. A pick-and-place position file for all components (top + bottom)

DNP (Do Not Populate) parts are removed from BOTH files.

Usage:
    make buy
    or: python3 export_bom.py
    (Run in the directory containing the .kicad_pro file)

Script location: <project>/export_bom.py (next to the Makefile)

Output (in <project>/pcbpower/, created automatically; NOT in output/):
    <project>_BOM_procurement.csv
    <project>_BOM_procurement.xlsx
    <project>-all-pos_procurement.csv

Notes:
    - Sourced and Placed are always left empty, for manual tracking.
    - DNP is read from the schematic only, by KiCad itself.
    - The position file contains exactly the parts in the BOM.
    - The log cross-checks the BOM against the position file.

Requirements:
    - kicad-cli (KiCad 8 or newer) in PATH
    - pandas, openpyxl
"""

__version__ = "1.6.0"

import os
import re
import sys
import logging
import subprocess
import xml.etree.ElementTree as ET

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Final BOM columns (order matters)
BOM_COLUMNS = ["Item", "Reference", "Value", "Footprint", "Description",
               "Quantity", "Sourced", "Placed", "MPN"]
BLANK_COLUMNS = ["Sourced", "Placed"]

# kicad-cli field names -> column labels
KICAD_FIELDS = ["${ITEM_NUMBER}", "Reference", "Value", "Footprint", "Description",
                "${QUANTITY}", "Sourced", "Placed", "MPN"]
KICAD_LABELS = BOM_COLUMNS


# -------------------- Helpers --------------------
def find_project_name(project_dir):
    for fname in sorted(os.listdir(project_dir)):
        if fname.endswith(".kicad_pro"):
            return os.path.splitext(fname)[0]
    return None


def check_kicad_cli():
    try:
        result = subprocess.run(["kicad-cli", "--version"], check=True,
                                capture_output=True, text=True, timeout=10)
        logger.info(f"KiCad CLI version: {result.stdout.strip()}")
    except FileNotFoundError:
        logger.error("❌ kicad-cli is not installed or not in PATH.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Error checking kicad-cli: {e}")
        sys.exit(1)


def run_command(cmd, expected_file):
    logger.info("Running: " + " ".join(cmd))
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=300)
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ kicad-cli failed (exit code {e.returncode})")
        if e.stderr:
            logger.error(e.stderr.strip())
        return False
    except subprocess.TimeoutExpired:
        logger.error("❌ kicad-cli timed out after 300 seconds")
        return False
    if not os.path.exists(expected_file):
        logger.error(f"❌ Expected file not found: {expected_file}")
        return False
    return True


def split_refs(ref_text):
    """'C1,C2 C3' -> [C1, C2, C3];  'R5-R8' -> [R5, R6, R7, R8]"""
    refs = []
    for token in re.split(r"[,\s]+", str(ref_text).strip()):
        if not token:
            continue
        m = re.fullmatch(r"([A-Za-z_#]+)(\d+)-(?:[A-Za-z_#]+)?(\d+)", token)
        if m and int(m.group(2)) <= int(m.group(3)):
            prefix, start, end = m.group(1), int(m.group(2)), int(m.group(3))
            refs.extend(f"{prefix}{n}" for n in range(start, end + 1))
        else:
            refs.append(token)
    return refs


# -------------------- BOM --------------------
def export_bom_csv(sch_file, csv_path, exclude_dnp):
    """Export the BOM with kicad-cli. With exclude_dnp=True, KiCad itself
    leaves out every symbol marked DNP in the schematic."""
    cmd = [
        "kicad-cli", "sch", "export", "bom", sch_file,
        "--group-by", "Value,Footprint",
        "--ref-range-delimiter", "",
        "--fields", ",".join(KICAD_FIELDS),
        "--labels", ",".join(KICAD_LABELS),
        "--output", csv_path,
    ]
    if exclude_dnp:
        cmd.insert(5, "--exclude-dnp")
    return run_command(cmd, csv_path)


def refs_in(df):
    refs = set()
    for r in df["Reference"]:
        refs.update(split_refs(r))
    return refs


def clean_bom(df):
    """Blank Sourced/Placed, renumber, fix order and types."""
    for col in KICAD_LABELS:
        if col not in df.columns:
            df[col] = ""
    for col in BLANK_COLUMNS:
        df[col] = ""
    df = df[BOM_COLUMNS].copy()
    df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce").fillna(0).astype(int)
    df["Item"] = range(1, len(df) + 1)
    return df


def _is_set(val):
    return str(val).strip().lower() in ("1", "true", "yes", "dnp")


def read_dnp_from_netlist(sch_file, tmp_xml):
    """Ask KiCad for the schematic netlist (XML). It lists every placed part
    of this project and marks DNP parts. Unlike the BOM export, it is not
    affected by the project's BOM settings, so DNP parts are always listed.
    Returns (all_refs, dnp_refs)."""
    cmd = ["kicad-cli", "sch", "export", "netlist", sch_file,
           "--format", "kicadxml", "--output", tmp_xml]
    if not run_command(cmd, tmp_xml):
        return None, None
    all_refs, dnp_refs = set(), set()
    root = ET.parse(tmp_xml).getroot()
    for comp in root.iter("comp"):
        ref = (comp.get("ref") or "").strip()
        if not ref or ref.startswith("#"):
            continue
        all_refs.add(ref)
        dnp = any(p.get("name", "").strip().lower() == "dnp" and _is_set(p.get("value", "1"))
                  for p in comp.findall("property"))
        if not dnp:   # also accept a text field called "DNP"
            dnp = any(f.get("name", "").strip().lower() == "dnp" and (f.text or "").strip()
                      and _is_set(f.text) for f in comp.iter("field"))
        if dnp:
            dnp_refs.add(ref)
    return all_refs, dnp_refs


def remove_refs_from_bom(df, dnp_refs):
    """Take DNP references out of each BOM row, fix Quantity, drop empty rows."""
    keep = []
    for i, row in df.iterrows():
        refs = split_refs(row["Reference"])
        fitted = [r for r in refs if r not in dnp_refs]
        if not fitted:
            continue
        if len(fitted) != len(refs):
            df.at[i, "Reference"] = ",".join(fitted)
            df.at[i, "Quantity"] = str(len(fitted))
        keep.append(i)
    return df.loc[keep].copy()


def write_excel(df, xlsx_path):
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="BOM")
        ws = writer.sheets["BOM"]
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        # Auto-size columns (capped so long reference lists don't explode)
        for col_cells in ws.columns:
            width = max(len(str(c.value)) if c.value is not None else 0 for c in col_cells)
            ws.column_dimensions[col_cells[0].column_letter].width = min(width + 2, 60)


# -------------------- Position file --------------------
def sort_refs(refs):
    """R2 before R10"""
    def key(r):
        m = re.match(r"([^\d]*)(\d*)", r)
        return (m.group(1), int(m.group(2)) if m.group(2) else 0, r)
    return sorted(refs, key=key)


def export_pos(pcb_file, pos_path, dnp_refs, bom_refs):
    cmd = [
        "kicad-cli", "pcb", "export", "pos", pcb_file,
        "--format", "csv", "--units", "mm", "--side", "both",
        "--output", pos_path,
    ]
    if not run_command(cmd, pos_path):
        return False

    try:
        pos = pd.read_csv(pos_path, dtype=str, keep_default_na=False)
    except pd.errors.EmptyDataError:
        logger.warning("⚠️  Position file is empty (no placeable parts?)")
        return True
    ref_col = "Ref" if "Ref" in pos.columns else pos.columns[0]
    pos[ref_col] = pos[ref_col].str.strip()

    in_bom = pos[ref_col].isin(bom_refs)
    removed = pos.loc[~in_bom, ref_col]
    if len(removed):
        dnp_part = [r for r in removed if r in dnp_refs]
        other = [r for r in removed if r not in dnp_refs]
        if dnp_part:
            logger.info(f"Removed {len(dnp_part)} DNP part(s) from position file: "
                        f"{', '.join(sort_refs(dnp_part))}")
        if other:
            logger.info(f"Removed {len(other)} part(s) not in the BOM (DNP or 'Exclude from BOM'): "
                        f"{', '.join(sort_refs(other))}")
    pos = pos[in_bom]
    pos.to_csv(pos_path, index=False)

    # Cross-check BOM vs position file
    missing = bom_refs - set(pos[ref_col])
    if missing:
        logger.warning(f"⚠️  {len(missing)} BOM part(s) NOT in position file (no footprint on PCB, "
                       f"or 'Exclude from position files' set): {', '.join(sort_refs(missing))}")
    else:
        logger.info("✅ Position file matches the BOM exactly")
    logger.info(f"✅ Position file: {pos_path}  ({len(pos)} parts)")
    return True


# -------------------- Main --------------------
def main():
    project_dir = os.getcwd()
    project_name = find_project_name(project_dir)
    if project_name is None:
        logger.error("❌ No .kicad_pro file found in the current directory.")
        sys.exit(1)

    sch_file = os.path.join(project_dir, f"{project_name}.kicad_sch")
    pcb_file = os.path.join(project_dir, f"{project_name}.kicad_pcb")
    for f in (sch_file, pcb_file):
        if not os.path.isfile(f):
            logger.error(f"❌ File not found: {f}")
            sys.exit(1)

    check_kicad_cli()

    # Saved in pcbpower/ (not output/), so the files made by
    # export_fab_outputs.py in output/ are never touched.
    out_dir = os.path.join(project_dir, "pcbpower")
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, f"{project_name}_BOM_procurement.csv")
    xlsx_path = os.path.join(out_dir, f"{project_name}_BOM_procurement.xlsx")
    pos_path = os.path.join(out_dir, f"{project_name}-all-pos_procurement.csv")

    logger.info(f"Exporting procurement BOM for project: {project_name}")
    tmp_xml = os.path.join(out_dir, ".netlist_tmp.xml")
    try:
        # 1) DNP list straight from KiCad's netlist (schematic only)
        all_refs, dnp_refs = read_dnp_from_netlist(sch_file, tmp_xml)
        if all_refs is None:
            logger.warning("⚠️  Could not read netlist; relying on KiCad's BOM for DNP")
            all_refs, dnp_refs = set(), set()
        else:
            logger.info(f"Schematic: {len(all_refs)} parts, {len(dnp_refs)} marked DNP")

        # 2) BOM from KiCad, with DNP parts removed (by KiCad and again here)
        if not export_bom_csv(sch_file, csv_path, exclude_dnp=True):
            logger.error("❌ Your kicad-cli may not support --exclude-dnp (needs KiCad 8 or newer).")
            sys.exit(1)
        df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
        df = remove_refs_from_bom(df, dnp_refs)
        bom_refs = refs_in(df)
        df = clean_bom(df)
        df.to_csv(csv_path, index=False)   # overwrite with the cleaned version
        write_excel(df, xlsx_path)
    except ET.ParseError as e:
        logger.error(f"❌ Could not read KiCad netlist: {e}")
        sys.exit(1)
    except pd.errors.EmptyDataError:
        logger.error(f"❌ BOM CSV is empty: {csv_path}")
        sys.exit(1)
    except PermissionError as e:
        logger.error(f"❌ Permission denied (is the Excel file open?): {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Error processing BOM: {e}")
        sys.exit(1)
    finally:
        if os.path.exists(tmp_xml):
            os.remove(tmp_xml)

    if dnp_refs:
        logger.info(f"DNP parts in schematic ({len(dnp_refs)}): {', '.join(sort_refs(dnp_refs))}")
    else:
        logger.info("No DNP parts found in schematic")
    logger.info(f"✅ BOM CSV:   {csv_path}")
    logger.info(f"✅ BOM Excel: {xlsx_path}  ({len(df)} line items, "
                f"{df['Quantity'].sum()} parts)")

    try:
        if not export_pos(pcb_file, pos_path, dnp_refs, bom_refs):
            sys.exit(1)
    except PermissionError as e:
        logger.error(f"❌ Permission denied (is the position file open?): {e}")
        sys.exit(1)


try:
    import pandas as pd
except ImportError:
    logger.error("❌ pandas is not installed. Run: pip install pandas openpyxl")
    sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.error("❌ Interrupted by user")
        sys.exit(130)
