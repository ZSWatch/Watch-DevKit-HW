"""
check-bom.py - Compare the components of a KiCad schematic with a generated
BOM (CSV / XLSX).

The schematic is read from the root sheet through the whole hierarchy. A
component is expected in the BOM when it is not excluded from the BOM, not
marked as DNP and fitted in the selected variant. The script fails when an
expected component is missing in the BOM, when the BOM lists a component that
is not expected, when a reference is listed twice, when a quantity does not
match its references or when several BOM files differ.

Usage:
    python check-bom.py -s <root>.kicad_sch -b <bom>.csv [-b <bom>.xlsx] [-v <variant>]
                        [-r <report>.md] [-c <checklist>.md]

Arguments:
    -s, --schematic     Root schematic (.kicad_sch).
    -b, --bom           BOM file (.csv or .xlsx). Can be given several times.
    -v, --variant       KiBoM style variant used to generate the BOM.
    --variant-field     Field with the variant information (default: Config).
    --ref-column        BOM column with the references (default: References).
    --qty-column        BOM column (prefix) with the quantity (default: Quantity).
    -r, --report        Write the detailed Markdown report to this file.
    -c, --checklist     Write the Markdown checklist to this file.
    -q, --quiet         Only print the result line.
    --no-fail           Always exit with 0, only report.

Exit codes:
    0   BOM matches the schematic
    1   BOM does not match the schematic
    2   Missing or unreadable input
"""

import re
import os
import sys
import csv
import zipfile
import textwrap
import argparse
import collections
import xml.etree.ElementTree as ET

# Values of the variant field that mark a component as not fitted (same list as KiBoM / KiBot)
DNF_KEYWORDS = {"dnf", "dnl", "dnp", "do not fit", "do not place", "do not load", "nofit", "nostuff",
                "noplace", "dni", "not fitted", "no stuff", "no place"}
XLSX_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

REASON_DNP = "Do not populate (DNP)"
REASON_VARIANT = "Not fitted in variant"
REASON_NOT_IN_BOM = "Other parts excluded from BOM"

# Classification of the fitted parts that are excluded from the BOM in the
# schematic: (reason, reference prefix, pattern for symbol name, value and footprint)
NOT_IN_BOM_CLASSES = [
    ("Test points", r"TP\d", r"test.?point"),
    ("Fiducials", r"FID\d", r"fiducial"),
    ("Mounting holes", None, r"mount.*hole"),
    ("Solder jumpers", None, r"solder.*(jump|bridge)"),
    ("Logos and graphics", None, r"logo|graphic"),
]


def parse_sexpr(text):
    """
    Parses a KiCad S-expression into nested lists. Quoted strings are returned
    without the quotes.
    """
    stack = [[]]
    for token in re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+', text):
        if token == "(":
            stack.append([])
        elif token == ")":
            node = stack.pop()
            stack[-1].append(node)
        elif token.startswith('"'):
            stack[-1].append(token[1:-1].replace('\\"', '"').replace("\\\\", "\\"))
        else:
            stack[-1].append(token)

    return stack[0][0]


def children(node, name):
    return [x for x in node[1:] if isinstance(x, list) and x and x[0] == name]


def child_value(node, name, default=None):
    found = children(node, name)
    return found[0][1] if found and len(found[0]) > 1 else default


def properties(node):
    return {p[1]: p[2] for p in children(node, "property") if len(p) > 2}


def variant_excluded(config, variant):
    """
    Evaluates a KiBoM style variant field ("dnf", "-VARIANT", "+VARIANT").
    """
    tokens = [t.strip().lower() for t in re.split(r"[,\s]+", config) if t.strip()]
    if config.strip().lower() in DNF_KEYWORDS or any(t in DNF_KEYWORDS for t in tokens):
        return True

    if not variant:
        return False

    variant = variant.lower()
    if "-" + variant in tokens:
        return True

    exclusive = [t[1:] for t in tokens if t.startswith("+")]

    return bool(exclusive) and variant not in exclusive


def not_in_bom_reason(reference, symbol, value, footprint):
    text = " ".join([symbol, value, footprint])
    for reason, prefix, pattern in NOT_IN_BOM_CLASSES:
        if (prefix and re.match(prefix, reference)) or re.search(pattern, text, re.IGNORECASE):
            return reason

    return REASON_NOT_IN_BOM


def read_schematic(root_file, variant, variant_field):
    """
    Walks the sheet hierarchy starting at the root schematic and returns all
    components (reference -> details). Sheets that are not part of the
    hierarchy and power symbols are ignored.
    """
    cache = {}
    components = {}

    def load(file_path):
        if file_path not in cache:
            with open(file_path, "r", encoding="utf-8") as f:
                cache[file_path] = parse_sexpr(f.read())

        return cache[file_path]

    def walk(file_path, path, sheet_name, sheet_in_bom, sheet_dnp, depth):
        if depth > 32:
            print(f"Error: Sheet hierarchy too deep at '{file_path}'.", file=sys.stderr)
            sys.exit(2)

        tree = load(file_path)

        for symbol in children(tree, "symbol"):
            props = properties(symbol)
            reference = props.get("Reference", "?")
            for instances in children(symbol, "instances"):
                for project in children(instances, "project"):
                    for instance in children(project, "path"):
                        if instance[1] == path:
                            reference = child_value(instance, "reference", reference)

            # Power symbols and other virtual parts
            if reference.startswith("#"):
                continue

            in_bom = sheet_in_bom and child_value(symbol, "in_bom", "yes") == "yes"
            dnp = sheet_dnp or child_value(symbol, "dnp", "no") == "yes"
            config = next((v for k, v in props.items() if k.lower() == variant_field.lower()), "")

            # DNP wins over "exclude from BOM", so not fitted parts are listed as such
            if dnp:
                reason = REASON_DNP
            elif variant_excluded(config, variant):
                reason = REASON_VARIANT
            elif not in_bom:
                reason = not_in_bom_reason(reference, child_value(symbol, "lib_id", ""),
                                           props.get("Value", ""), props.get("Footprint", ""))
            else:
                reason = None

            # Multi-unit symbols share one reference
            if reference in components and components[reference]["reason"] is None:
                continue

            components[reference] = {
                "value": props.get("Value", ""),
                "symbol": child_value(symbol, "lib_id", ""),
                "footprint": props.get("Footprint", ""),
                "sheet": sheet_name,
                "reason": reason,
            }

        for sheet in children(tree, "sheet"):
            props = properties(sheet)
            sheet_file = os.path.join(os.path.dirname(file_path), props.get("Sheetfile", ""))
            if not os.path.isfile(sheet_file):
                print(f"Error: Sheet file '{sheet_file}' not found.", file=sys.stderr)
                sys.exit(2)

            walk(sheet_file,
                 path + "/" + child_value(sheet, "uuid", ""),
                 props.get("Sheetname", os.path.basename(sheet_file)),
                 sheet_in_bom and child_value(sheet, "in_bom", "yes") == "yes",
                 sheet_dnp or child_value(sheet, "dnp", "no") == "yes",
                 depth + 1)

    root = load(os.path.abspath(root_file))
    walk(os.path.abspath(root_file), "/" + child_value(root, "uuid", ""), "Root", True, False, 0)

    return components


def split_references(text):
    """
    Splits a BOM reference cell ("R1 R2", "R1, R2" or "R1-R3") into single
    references.
    """
    references = []
    for item in re.split(r"[,;\s]+", text.strip()):
        if not item:
            continue

        match = re.fullmatch(r"([A-Za-z_]+)(\d+)-\1?(\d+)", item)
        if match and int(match.group(2)) < int(match.group(3)):
            references += [f"{match.group(1)}{i}" for i in range(int(match.group(2)), int(match.group(3)) + 1)]
        else:
            references.append(item)

    return references


def read_csv_rows(file_path):
    with open(file_path, "r", encoding="utf-8-sig", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel

        return [list(csv.reader(f, dialect))]


def read_xlsx_rows(file_path):
    """
    Returns the rows of all worksheets. Only uses the standard library, so it
    also runs inside minimal CI containers.
    """
    sheets = []
    with zipfile.ZipFile(file_path) as archive:
        strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            for item in ET.fromstring(archive.read("xl/sharedStrings.xml")).iter(XLSX_NS + "si"):
                strings.append("".join(t.text or "" for t in item.iter(XLSX_NS + "t")))

        names = sorted((n for n in archive.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n)),
                       key=lambda n: int(re.search(r"\d+", n).group()))
        for name in names:
            rows = []
            for row in ET.fromstring(archive.read(name)).iter(XLSX_NS + "row"):
                cells = {}
                for cell in row.iter(XLSX_NS + "c"):
                    column = 0
                    for char in re.match(r"[A-Z]+", cell.get("r")).group():
                        column = column * 26 + ord(char) - 64

                    value = cell.find(XLSX_NS + "v")
                    if cell.get("t") == "s" and value is not None:
                        cells[column] = strings[int(value.text)]
                    elif cell.get("t") == "inlineStr":
                        cells[column] = "".join(t.text or "" for t in cell.iter(XLSX_NS + "t"))
                    elif value is not None:
                        cells[column] = value.text or ""

                rows.append([cells.get(i, "") for i in range(1, max(cells, default=0) + 1)])

            sheets.append(rows)

    return sheets


def read_bom(file_path, ref_column, qty_column):
    """
    Returns the references listed in a CSV or XLSX BOM and a list of problems
    found inside the BOM itself (duplicates, wrong quantities).
    """
    tables = read_xlsx_rows(file_path) if file_path.lower().endswith(".xlsx") else read_csv_rows(file_path)

    for rows in tables:
        for index, header in enumerate(rows):
            names = [str(c).strip().lower() for c in header]
            if ref_column.lower() not in names:
                continue

            ref_index = names.index(ref_column.lower())
            qty_index = next((i for i, n in enumerate(names) if n.startswith(qty_column.lower())), None)
            references = []
            problems = []
            for row in rows[index + 1:]:
                if len(row) <= ref_index or not str(row[ref_index]).strip():
                    continue

                # Summary lines below the table (e.g. "Component Count:") have no row number
                if names[0] == "row" and not str(row[0]).strip().isdigit():
                    continue

                row_references = split_references(str(row[ref_index]))
                references += row_references
                if qty_index is not None and len(row) > qty_index:
                    try:
                        quantity = int(float(row[qty_index]))
                    except ValueError:
                        continue

                    if quantity != len(row_references):
                        problems.append(f"Quantity {quantity} does not match {len(row_references)} "
                                        f"references ({' '.join(row_references[:5])} ...)")

            duplicates = sorted(r for r, n in collections.Counter(references).items() if n > 1)
            if duplicates:
                problems.append("References listed more than once: " + " ".join(duplicates))

            return references, problems

    print(f"Error: No column '{ref_column}' found in '{file_path}'.", file=sys.stderr)
    sys.exit(2)


def natural_key(reference):
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", reference)]


def compress_references(references):
    """
    Shortens a list of references for the output ("TP1 TP2 TP3" -> "TP1-TP3").
    """
    result = []
    run = []

    def flush():
        if len(run) >= 3:
            result.append(f"{run[0]}-{run[-1]}")
        else:
            result.extend(run)

    for reference in sorted(references, key=natural_key):
        match = re.fullmatch(r"(\D+)(\d+)", reference)
        previous = re.fullmatch(r"(\D+)(\d+)", run[-1]) if run else None
        if (match and previous and match.group(1) == previous.group(1)
                and int(match.group(2)) == int(previous.group(2)) + 1):
            run.append(reference)
        else:
            flush()
            run = [reference]

    flush()

    return result


def evaluate(components, boms):
    """
    Compares the schematic with all BOM files and collects the results for the
    different outputs.
    """
    expected = {r for r, c in components.items() if c["reason"] is None}
    excluded = collections.defaultdict(list)
    for reference, component in components.items():
        if component["reason"]:
            excluded[component["reason"]].append(reference)

    files = []
    for file_path, (references, problems) in boms.items():
        listed = set(references)
        missing = sorted(expected - listed, key=natural_key)
        unexpected = sorted(listed - expected, key=natural_key)
        files.append({
            "path": file_path,
            "name": os.path.basename(file_path),
            "listed": listed,
            "missing": missing,
            "unexpected": unexpected,
            "problems": problems,
            "ok": not (missing or unexpected or problems),
        })

    differences = []
    for entry in files[1:]:
        difference = sorted(entry["listed"] ^ files[0]["listed"], key=natural_key)
        if difference:
            differences.append((entry["name"], files[0]["name"], difference))

    return {
        "expected": expected,
        "excluded": {reason: sorted(excluded[reason], key=natural_key) for reason in sorted(excluded)},
        "files": files,
        "differences": differences,
        "failed": bool(differences) or not all(entry["ok"] for entry in files),
    }


def unexpected_reason(components, reference):
    return components[reference]["reason"] if reference in components else "Not in schematic"


def build_console(schematic, variant, components, result):
    """
    Plain text output for the CI/CD log.
    """
    def wrapped(references, indent):
        return textwrap.fill(" ".join(compress_references(references)), width=100,
                             initial_indent=indent, subsequent_indent=indent)

    excluded = result["excluded"]
    rows = [("Components in schematic", len(components)),
            ("Expected in BOM", len(result["expected"])),
            ("Not expected in BOM", len(components) - len(result["expected"]))]
    rows += [("  " + reason, len(references)) for reason, references in excluded.items()]
    width = max(len(label) for label, _ in rows)

    lines = ["BOM check", "=========", "",
             f"Schematic: {schematic}" + (f" (variant {variant})" if variant else ""), ""]
    lines += [f"  {label:<{width}}  {count:>5}" for label, count in rows]

    lines += ["", "BOM files:"]
    width = max(len(entry["name"]) for entry in result["files"])
    for entry in result["files"]:
        lines.append(f"  [{'PASS' if entry['ok'] else 'FAIL'}] {entry['name']:<{width}}  "
                     f"{len(entry['listed'])} listed, {len(entry['missing'])} missing, "
                     f"{len(entry['unexpected'])} unexpected")

    for entry in result["files"]:
        if entry["ok"]:
            continue

        lines += ["", f"{entry['name']}:"]
        if entry["missing"]:
            lines.append(f"  Missing in BOM ({len(entry['missing'])}):")
            table = [(r, components[r]["value"], components[r]["symbol"], components[r]["sheet"])
                     for r in entry["missing"]]
            widths = [max(len(row[i]) for row in table) for i in range(3)]
            lines += [f"    {r:<{widths[0]}}  {v:<{widths[1]}}  {s:<{widths[2]}}  {sheet}" for r, v, s, sheet in table]

        if entry["unexpected"]:
            lines.append(f"  Unexpected in BOM ({len(entry['unexpected'])}):")
            width = max(len(r) for r in entry["unexpected"])
            lines += [f"    {r:<{width}}  {unexpected_reason(components, r)}" for r in entry["unexpected"]]

        if entry["problems"]:
            lines.append("  Problems inside the BOM:")
            lines += [f"    {p}" for p in entry["problems"]]

    for name, first, difference in result["differences"]:
        lines += ["", f"{name} differs from {first}:", wrapped(difference, "  ")]

    if excluded:
        lines += ["", "Not expected in BOM:"]
        for reason, references in excluded.items():
            lines += [f"  {reason} ({len(references)}):", wrapped(references, "    ")]

    lines += ["", "Result: " + ("FAIL - the BOM does not match the schematic" if result["failed"]
                                else "PASS - the BOM matches the schematic")]

    return "\n".join(lines)


def build_report(schematic, variant, components, result):
    """
    Detailed Markdown report (e.g. for the job summary).
    """
    lines = ["# BOM Check: " + ("FAIL" if result["failed"] else "PASS"), "",
             f"Schematic: `{schematic}`" + (f", variant `{variant}`" if variant else ""), "",
             "| | Count |", "| --- | --- |",
             f"| Components in schematic | {len(components)} |",
             f"| Expected in BOM | {len(result['expected'])} |",
             f"| Not expected in BOM | {len(components) - len(result['expected'])} |"]
    for reason, references in result["excluded"].items():
        lines.append(f"| &nbsp;&nbsp;{reason} | {len(references)} |")

    lines += ["", "| BOM file | Result | Listed | Missing | Unexpected |", "| --- | --- | --- | --- | --- |"]
    for entry in result["files"]:
        lines.append(f"| `{entry['name']}` | {'PASS' if entry['ok'] else 'FAIL'} | {len(entry['listed'])} | "
                     f"{len(entry['missing'])} | {len(entry['unexpected'])} |")

    for entry in result["files"]:
        if entry["ok"]:
            continue

        lines += ["", f"## `{entry['name']}`"]
        if entry["missing"]:
            lines += ["", "**Missing in BOM:**", "",
                      "| Reference | Value | Symbol | Footprint | Sheet |", "| --- | --- | --- | --- | --- |"]
            for reference in entry["missing"]:
                c = components[reference]
                lines.append(f"| {reference} | {c['value']} | {c['symbol']} | {c['footprint']} | {c['sheet']} |")

        if entry["unexpected"]:
            lines += ["", "**Unexpected in BOM:**", "", "| Reference | Reason |", "| --- | --- |"]
            lines += [f"| {r} | {unexpected_reason(components, r)} |" for r in entry["unexpected"]]

        if entry["problems"]:
            lines += ["", "**Problems inside the BOM:**", ""] + [f"- {p}" for p in entry["problems"]]

    for name, first, difference in result["differences"]:
        lines += ["", f"**`{name}` differs from `{first}`:** " + " ".join(difference)]

    for reason, references in result["excluded"].items():
        lines += ["", f"<details><summary>{reason} ({len(references)})</summary>", "",
                  "| Reference | Value | Symbol | Sheet |", "| --- | --- | --- | --- |"]
        for reference in references:
            c = components[reference]
            lines.append(f"| {reference} | {c['value']} | {c['symbol']} | {c['sheet']} |")

        lines += ["", "</details>"]

    return "\n".join(lines) + "\n"


def build_checklist(schematic, variant, components, result):
    """
    Markdown checklist that is stored together with the production data.
    """
    def item(ok, text, details=()):
        return [f"- [{'x' if ok else ' '}] {text}"] + [f"  - {d}" for d in details]

    lines = ["# BOM Checklist", "",
             f"- Schematic: `{os.path.basename(schematic)}`"]
    if variant:
        lines.append(f"- Variant: `{variant}`")

    lines += [f"- Result: **{'FAIL' if result['failed'] else 'PASS'}**", "",
              "## Automatic Checks", "",
              "A ticked box is a passed check."]

    for entry in result["files"]:
        lines += ["", f"### `{entry['name']}`", ""]
        lines += item(not entry["missing"],
                      f"All {len(result['expected'])} expected components are listed",
                      [f"Missing: {r} ({components[r]['value']}, {components[r]['symbol']}, "
                       f"sheet {components[r]['sheet']})" for r in entry["missing"]])
        lines += item(not entry["unexpected"], "No unexpected components are listed",
                      [f"Unexpected: {r} ({unexpected_reason(components, r)})" for r in entry["unexpected"]])
        lines += item(not entry["problems"], "Every reference is listed once and the quantities match",
                      entry["problems"])

    if len(result["files"]) > 1:
        lines += ["", "### All BOM Files", ""]
        lines += item(not result["differences"], "All BOM files list the same components",
                      [f"`{name}` differs from `{first}`: " + " ".join(difference)
                       for name, first, difference in result["differences"]])

    if result["excluded"]:
        lines += ["", "## Manual Review", "",
                  "Components of the schematic that are not expected in the BOM. Tick a group when it is "
                  "intended that these components are not in the BOM.", ""]
        for reason, references in result["excluded"].items():
            lines.append(f"- [ ] {reason} ({len(references)}): " + ", ".join(compress_references(references)))

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(
        description="Compare the components of a KiCad schematic with a generated BOM (CSV / XLSX). "
                    "Fails when a fitted component is missing in the BOM or the BOM lists "
                    "components that must not be in there.")
    parser.add_argument("-s", "--schematic", required=True, help="Root schematic (.kicad_sch)")
    parser.add_argument("-b", "--bom", required=True, action="append", help="BOM file (.csv or .xlsx), repeatable")
    parser.add_argument("-v", "--variant", default="", help="KiBoM style variant used to generate the BOM")
    parser.add_argument("--variant-field", default="Config", help="Field with the variant information")
    parser.add_argument("--ref-column", default="References", help="BOM column with the references")
    parser.add_argument("--qty-column", default="Quantity", help="BOM column (prefix) with the quantity")
    parser.add_argument("-r", "--report", help="Write the detailed Markdown report to this file")
    parser.add_argument("-c", "--checklist", help="Write the Markdown checklist to this file")
    parser.add_argument("-q", "--quiet", action="store_true", help="Only print the result line")
    parser.add_argument("--no-fail", action="store_true", help="Always exit with 0, only report")
    args = parser.parse_args()

    for file_path in [args.schematic] + args.bom:
        if not os.path.isfile(file_path):
            print(f"Error: File '{file_path}' not found.", file=sys.stderr)
            sys.exit(2)

    components = read_schematic(args.schematic, args.variant, args.variant_field)
    boms = {b: read_bom(b, args.ref_column, args.qty_column) for b in args.bom}
    result = evaluate(components, boms)

    console = build_console(args.schematic, args.variant, components, result)
    print(console.splitlines()[-1] if args.quiet else console)

    for file_path, content in ((args.report, build_report), (args.checklist, build_checklist)):
        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content(args.schematic, args.variant, components, result))

    if result["failed"] and not args.no_fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
