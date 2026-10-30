#!/usr/bin/env python3
"""
check_pages.py - Check and fix the page numbers of a KiCad schematic hierarchy.

Usage:
    python3 check_pages.py <root>.kicad_sch [--fix]

Checks:
    1. Page numbers: the sheets of the hierarchy (seen from the root sheet) must be numbered
       1, 2, 3, ... without gaps or duplicates, e.g. after a sheet was removed or added.
       The order of the current numbers is kept.
    2. Page links: texts with a link to a page ('(href "#<page>")', e.g. "Page 7" next to a sheet
       symbol) must point to the page of the sheet symbol they belong to (the nearest sheet symbol
       on the same sheet, at most MAX_LINK_DISTANCE away). A number in the text is updated as well.
       Texts with variables (e.g. "${SHEET_NAME_7}") and texts that are not next to a sheet symbol
       (e.g. the page numbers of the table of contents) are skipped, they follow the page numbers.

Without --fix only the differences are printed. With --fix the schematic files are updated.
Only the instances of the root sheet are changed, instances of other projects stay untouched.

Exit codes:
    0   Page numbers and links are correct (or were fixed with --fix)
    1   Differences found (without --fix)
    2   Unreadable input
"""

import os
import re
import sys

BS = chr(92)

# Maximum distance (mm) between a page link and the border of its sheet symbol
MAX_LINK_DISTANCE = 12.7


def block_end(text, start):
    """Index after the closing parenthesis of the expression that starts at text[start]"""
    depth = 0
    in_string = False
    i = start
    while i < len(text):
        c = text[i]
        if in_string:
            if c == BS:
                i += 1
            elif c == '"':
                in_string = False
        elif c == '"':
            in_string = True
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise ValueError("Unbalanced parentheses")


def children(text, start, end):
    """(start, end) of the direct child expressions of the expression text[start:end]"""
    result = []
    i = start + 1
    while i < end - 1:
        c = text[i]
        if c == "(":
            e = block_end(text, i)
            result.append((i, e))
            i = e
        elif c == '"':
            i += 1
            while text[i] != '"':
                i += 2 if text[i] == BS else 1
            i += 1
        else:
            i += 1
    return result


def head(text, start):
    """Keyword of the expression at text[start]"""
    return re.match(r"\(([A-Za-z_]+)", text[start:start + 40]).group(1)


class Sheet:
    """One schematic file"""

    def __init__(self, path):
        self.path = path
        with open(path, encoding="utf-8", newline="") as f:
            raw = f.read()
        self.crlf = "\r\n" in raw
        self.text = raw.replace("\r\n", "\n")
        # Parsed once, the positions refer to the unchanged text
        self._symbols = None

    def top(self):
        root = self.text.index("(kicad_sch")
        return children(self.text, root, block_end(self.text, root))

    def uuid(self):
        for s, e in self.top():
            if head(self.text, s) == "uuid":
                return re.search(r'"([^"]+)"', self.text[s:e]).group(1)
        raise ValueError("No uuid in %s" % self.path)

    def sheet_symbols(self):
        """Sheet symbols: name, file, uuid, position, size, instances [(path, page, span of the page string)]"""
        if self._symbols is not None:
            return self._symbols
        result = []
        for s, e in self.top():
            if head(self.text, s) != "sheet":
                continue
            info ={"name": None, "file": None, "uuid": None, "at": None, "size": None, "instances": []}
            for cs, ce in children(self.text, s, e):
                key = head(self.text, cs)
                part = self.text[cs:ce]
                if key == "uuid":
                    info["uuid"] = re.search(r'"([^"]+)"', part).group(1)
                elif key == "at":
                    info["at"] = tuple(map(float, re.findall(r"[-\d.]+", part)[:2]))
                elif key == "size":
                    info["size"] = tuple(map(float, re.findall(r"[-\d.]+", part)[:2]))
                elif key == "property":
                    m = re.match(r'\(property "(Sheetname|Sheetfile)" "((?:[^"\\]|\\.)*)"', part)
                    if m:
                        info["name" if m.group(1) == "Sheetname" else "file"] = m.group(2)
                elif key == "instances":
                    for m in re.finditer(r'\(path "([^"]*)"\s*\(page "([^"]*)"\)', part):
                        info["instances"].append((m.group(1), m.group(2), cs + m.start(2), cs + m.end(2)))
            if info["file"] is None:
                raise ValueError("Sheet symbol without file in %s" % self.path)
            result.append(info)
        self._symbols = result
        return result

    def save(self):
        text = self.text.replace("\n", "\r\n") if self.crlf else self.text
        with open(self.path, "w", encoding="utf-8", newline="") as f:
            f.write(text)


def main():
    args = [a for a in sys.argv[1:] if a != "--fix"]
    fix = "--fix" in sys.argv[1:]
    if len(args) != 1 or not args[0].endswith(".kicad_sch"):
        sys.exit(__doc__)
    root_path = os.path.abspath(args[0])
    directory = os.path.dirname(root_path)

    files = {}

    def load(path):
        path = os.path.normpath(path)
        if path not in files:
            files[path] = Sheet(path)
        return files[path]

    try:
        root = load(root_path)
        root_uuid = root.uuid()
    except (OSError, ValueError) as e:
        print("Can not read %s: %s" % (root_path, e), file=sys.stderr)
        sys.exit(2)

    # Walk the hierarchy: (page, order, name, file, instance path, file of the symbol, symbol)
    pages = []

    def walk(sheet, path, trail):
        for symbol in sheet.sheet_symbols():
            instance = [i for i in symbol["instances"] if i[0] == path]
            if not instance:
                print("Warning: no instance of sheet '%s' for path %s in %s" % (symbol["name"], path,
                      os.path.basename(sheet.path)))
                continue
            child_file = os.path.normpath(os.path.join(os.path.dirname(sheet.path), symbol["file"]))
            pages.append({"page": instance[0][1], "order": len(pages), "name": symbol["name"],
                          "sheet": sheet, "span": instance[0][2:], "symbol": symbol,
                          "path": path + "/" + symbol["uuid"]})
            if child_file in trail:
                print("Warning: recursive sheet %s" % symbol["file"])
                continue
            walk(load(child_file), path + "/" + symbol["uuid"], trail | {child_file})

    try:
        walk(root, "/" + root_uuid, {os.path.normpath(root_path)})
    except (OSError, ValueError) as e:
        print("Can not read the hierarchy: %s" % e, file=sys.stderr)
        sys.exit(2)

    # 1. Page numbers: keep the current order, number them 2, 3, ... (the root sheet is page 1)
    def sort_key(p):
        return (int(p["page"]) if p["page"].isdigit() else 10 ** 6, p["order"])

    differences = 0
    expected = {}
    edits = {}
    for number, entry in enumerate(sorted(pages, key=sort_key), start=2):
        expected[id(entry["symbol"]), entry["sheet"].path] = str(number)
        if entry["page"] != str(number):
            differences += 1
            print("Page:  '%s' (%s) is page %s, expected %d" % (entry["name"], entry["symbol"]["file"],
                  entry["page"], number))
            edits.setdefault(entry["sheet"].path, []).append((entry["span"][0], entry["span"][1], str(number)))

    # 2. Page links: texts with href "#<page>" next to a sheet symbol
    link_edits = {}
    for path, sheet in list(files.items()):
        symbols = [s for s in sheet.sheet_symbols() if s["at"] and s["size"]
                   and (id(s), sheet.path) in expected]
        if not symbols:
            continue
        for s, e in sheet.top():
            if head(sheet.text, s) not in ("text", "text_box"):
                continue
            block = sheet.text[s:e]
            href = re.search(r'\(href "#(\d+)"\)', block)
            m = re.match(r'\((?:text|text_box) "((?:[^"\\]|\\.)*)"', block)
            if not href or not m or "${" in m.group(1):
                continue
            at = re.search(r'\(at ([-\d.]+) ([-\d.]+)', block)
            x, y = float(at.group(1)), float(at.group(2))

            def distance(sym):
                sx, sy = sym["at"]
                w, h = sym["size"]
                dx = max(sx - x, 0, x - sx - w)
                dy = max(sy - y, 0, y - sy - h)
                return dx * dx + dy * dy

            nearest = min(symbols, key=distance)
            # Only texts next to a sheet symbol belong to it (e.g. not the table of contents)
            if distance(nearest) > MAX_LINK_DISTANCE ** 2:
                continue
            page = expected[id(nearest), sheet.path]
            label = m.group(1)
            new_label = re.sub(r"\d+", page, label, count=1) if re.fullmatch(r"\D*\d+\D*", label) else label
            if href.group(1) != page or new_label != label:
                differences += 1
                print("Link:  '%s' -> #%s at (%g, %g) in %s belongs to '%s' (page %s)" % (
                      label, href.group(1), x, y, os.path.basename(sheet.path), nearest["name"], page))
                link_edits.setdefault(sheet.path, []).append((s + m.start(1), s + m.end(1), new_label))
                link_edits[sheet.path].append((s + href.start(1), s + href.end(1), page))

    if differences == 0:
        print("Page numbers and page links are correct (%d sheets)" % (len(pages) + 1))
        sys.exit(0)

    if not fix:
        print("%d difference(s), run with --fix to correct them" % differences)
        sys.exit(1)

    for path in set(edits) | set(link_edits):
        sheet = files[path]
        for start, end, value in sorted(edits.get(path, []) + link_edits.get(path, []), reverse=True):
            sheet.text = sheet.text[:start] + value + sheet.text[end:]
        sheet.save()
        print("Updated %s" % os.path.relpath(path, directory))
    sys.exit(0)


if __name__ == "__main__":
    main()
