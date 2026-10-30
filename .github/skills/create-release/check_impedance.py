#!/usr/bin/env python3
"""
check_impedance.py - Check the impedance table of the fabrication documents against the layout.

Usage:
    python3 check_impedance.py <board>.kicad_pro <impedance_table.txt> [--tolerance <percent>] [--write]

The net classes of the project named '<Bus>_<Impedance>' (e.g. 'USB_90', 'Ethernet_100') define the
transmission lines with controlled impedance. Net classes without impedance (e.g. 'GND', 'I2C') are
ignored. For every such net class the script determines from the layout (<board>.kicad_pcb next to
the project):

    Transmission Line   Bus name of the net class ('USB')
    Impedance [ohms]    Impedance of the net class ('90')
    Tolerance [%]       Not stored in the project: taken from the existing row of the table or
                        from --tolerance, otherwise unknown ('?')
    Layer               Copper layer(s) with tracks of the net class, one row per layer
    Trace Width [mm]    Width of these tracks
    Gap [mm]            Diff pair gap of the net class, '-' for single ended lines
    Ref. Layers         Neighbouring copper layers in the stackup with a zone of a ground net
                        (name contains 'GND'), otherwise unknown ('?')

Without --write the expected rows are compared with the table. With --write the rows of the table are
replaced by the expected rows (only possible when no value is unknown). The header line is kept.

Problems that need a decision of the user are reported and make the check fail:
    - a value is unknown ('?')
    - a net class with impedance has no routed tracks (unused net class)
    - the tracks of a net class use a width that differs from the net class

Exit codes:
    0   Table matches the layout (or was written with --write)
    1   Differences or problems found
    2   Unreadable input
"""

import fnmatch
import json
import os
import re
import sys

IMPEDANCE_CLASS = re.compile(r"^(?P<bus>.+)_(?P<impedance>\d+(?:\.\d+)?)$")
STRING = r'"((?:[^"\\]|\\.)*)"'


def fmt(value):
    """Number in the notation of KiCad (0.239, 0.2)"""
    return ("%.4f" % float(value)).rstrip("0").rstrip(".")


def netclass_of(net, classes, patterns, assignments):
    """Net class of a net like KiCad: explicit assignment, then the pattern of the highest priority"""
    if net in assignments:
        names = assignments[net]
        names = names if isinstance(names, list) else [names]
        names = [n for n in names if n in classes]
        if names:
            return min(names, key=lambda n: classes[n].get("priority", 1 << 31))
    hits = [p["netclass"] for p in patterns
            if p.get("netclass") in classes and fnmatch.fnmatchcase(net, p.get("pattern", ""))]
    if hits:
        return min(hits, key=lambda n: classes[n].get("priority", 1 << 31))
    return "Default"


def read_table(path):
    with open(path, encoding="utf-8", newline="") as f:
        raw = f.read()
    newline = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.replace("\r\n", "\n").split("\n")
    header = lines[0]
    rows = [[cell.strip() for cell in line.split(",")] for line in lines[1:] if line.strip()]
    return header, rows, newline


def aligned(header, values):
    """Row with the same tab alignment as the header (tab stops of 8)"""
    columns = []
    pos = 0
    for part in header.split(","):
        text = part.lstrip("\t")
        for _ in range(len(part) - len(text)):
            pos = (pos // 8 + 1) * 8
        columns.append(pos)
        pos += len(text) + 1
    out = ""
    pos = 0
    for i, value in enumerate(values):
        if i:
            out += ",\t"
            pos = ((pos + 1) // 8 + 1) * 8
            while i < len(columns) and pos < columns[i]:
                out += "\t"
                pos = (pos // 8 + 1) * 8
        out += value
        pos += len(value)
    return out


def main():
    args = sys.argv[1:]
    write = "--write" in args
    args = [a for a in args if a != "--write"]
    tolerance = None
    if "--tolerance" in args:
        i = args.index("--tolerance")
        tolerance = args[i + 1]
        del args[i:i + 2]
    if len(args) != 2 or not args[0].endswith(".kicad_pro"):
        sys.exit(__doc__)
    pro_path, table_path = args
    pcb_path = pro_path[:-len(".kicad_pro")] + ".kicad_pcb"

    try:
        with open(pro_path, encoding="utf-8") as f:
            settings = json.load(f)["net_settings"]
        with open(pcb_path, encoding="utf-8") as f:
            pcb = f.read().replace("\r\n", "\n")
        header, table, newline = read_table(table_path)
    except (OSError, KeyError, ValueError) as e:
        print("Can not read the input: %s" % e, file=sys.stderr)
        sys.exit(2)

    classes = {c["name"]: c for c in settings.get("classes", [])}
    patterns = settings.get("netclass_patterns") or []
    assignments = settings.get("netclass_assignments") or {}
    impedance = {name: IMPEDANCE_CLASS.match(name) for name in classes if IMPEDANCE_CLASS.match(name)}

    # Net names by number (older files) for tracks that reference the net by number
    numbers = dict(re.findall(r'\n\t\(net (\d+) ' + STRING + r'\)', pcb))

    # Tracks of the net classes with impedance: {class: {(layer, width): count}}
    tracks = {name: {} for name in impedance}
    for m in re.finditer(r"\n\t\((?:segment|arc)\n(.*?)\n\t\)", pcb, re.S):
        block = m.group(1)
        net = re.search(r'\(net ' + STRING + r'\)', block)
        if net:
            net = net.group(1)
        else:
            number = re.search(r"\(net (\d+)\)", block)
            net = numbers.get(number.group(1)) if number else None
        if not net:
            continue
        name = netclass_of(net, classes, patterns, assignments)
        if name in tracks:
            key = (re.search(r'\(layer ' + STRING + r'\)', block).group(1),
                   fmt(re.search(r"\(width ([\d.]+)\)", block).group(1)))
            tracks[name][key] = tracks[name].get(key, 0) + 1

    # Copper layers in the order of the stackup and the layers with a ground zone
    stackup = re.search(r"\n\t\t\(stackup\n(.*?)\n\t\t\)", pcb, re.S)
    copper = []
    if stackup:
        for m in re.finditer(r'\(layer ' + STRING + r'(.*?)\n\t\t\t\)', stackup.group(1), re.S):
            if re.search(r'\(type "copper"\)', m.group(2)):
                copper.append(m.group(1))
    ground = set()
    for m in re.finditer(r"\n\t\(zone\n(.*?)\n\t\)", pcb, re.S):
        block = m.group(1)
        net = re.search(r'\(net_name ' + STRING + r'\)', block) or re.search(r'\(net ' + STRING + r'\)', block)
        if net and "GND" in net.group(1).upper():
            layers = re.search(r'\(layers? ((?:"[^"]*"\s*)+)\)', block)
            if layers:
                ground.update(re.findall(STRING, layers.group(1)))

    def reference_layers(layer):
        if layer not in copper:
            return "?"
        i = copper.index(layer)
        refs = [copper[j] for j in (i - 1, i + 1) if 0 <= j < len(copper) and copper[j] in ground]
        return " / ".join(refs) if refs else "?"

    existing = {row[0]: row for row in table if row}
    problems = []
    expected = []
    for name in sorted(impedance, key=str.lower):
        m = impedance[name]
        bus, ohms = m.group("bus"), m.group("impedance")
        cls = classes[name]
        if cls.get("diff_pair_width") is not None:
            width, gap = fmt(cls["diff_pair_width"]), fmt(cls.get("diff_pair_gap", 0))
        else:
            width = fmt(cls["track_width"]) if cls.get("track_width") is not None else "?"
            gap = "-"
        used = tracks[name]
        if not used:
            problems.append("Net class '%s' has an impedance, but no routed tracks. Ask the user whether "
                            "it can be removed from the project" % name)
            continue
        for layer in sorted({layer for layer, _ in used}, key=lambda l: copper.index(l) if l in copper else 99):
            widths = sorted({w for l, w in used if l == layer})
            if widths != [width]:
                problems.append("Net class '%s' has the width %s mm, the tracks on %s use %s mm" % (
                    name, width, layer, ", ".join(widths)))
            old = existing.get(bus)
            tol = tolerance or (old[2] if old and len(old) > 2 and old[2] else "?")
            expected.append([bus, ohms, tol, layer, width, gap, reference_layers(layer)])

    columns = [c.strip() for c in header.split(",")]
    for row in expected:
        for column, value in zip(columns, row):
            if value == "?":
                problems.append("Unknown value '%s' of '%s' on %s, ask the user" % (column, row[0], row[3]))

    current = [row for row in table if row]
    differs = [r[:7] for r in current] != expected

    print("Expected rows:")
    for row in expected:
        print("    " + ", ".join(row))
    print("Rows in %s:" % os.path.basename(table_path))
    for row in current:
        print("    " + ", ".join(row))
    if not current:
        print("    (none)")
    for problem in problems:
        print("Problem: " + problem)

    if write:
        if any("?" in row for row in expected):
            print("Not written: unknown values must be given first (e.g. --tolerance)", file=sys.stderr)
            sys.exit(1)
        with open(table_path, "w", encoding="utf-8", newline="") as f:
            f.write(newline.join([header] + [aligned(header, row) for row in expected]) + newline)
        print("Updated %s" % table_path)
        sys.exit(1 if problems else 0)

    if differs or problems:
        if differs:
            print("The table differs from the layout, run with --write to update it")
        sys.exit(1)
    print("Impedance table matches the layout (%d rows)" % len(expected))
    sys.exit(0)


if __name__ == "__main__":
    main()
