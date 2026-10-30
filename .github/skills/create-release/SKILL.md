---
name: create-release
description: Create a hardware release x.y.z of this KiCad project. Runs ERC/DRC, checks and fixes the page numbers of the schematic, checks the impedance table against the net classes of the layout, sets the changelog variables of the release in the KiBot configuration and the schematic, switches the KiBot variant to CHECKED, pushes "Prepare Release x.y.z" to the development branch, waits for the KiBot pipeline, merges into the main branch, creates and pushes the tag x.y.z, waits for the release pipeline, pulls the released state of the main branch and finishes with the main branch checked out. Use when the user asks to prepare, create or publish a release.
---

# Create Release

Releases are built by the `Hardware / PCB Data` workflow ([hw-pcb.yaml](../../workflows/hw-pcb.yaml)).
A push to the development branch builds the outputs with the variant from `kibot_variant`,
a push of a SemVer tag (`x.y.z`) builds the `RELEASED` variant, updates the `CHANGELOG.md`
and creates the GitHub release.

## Prerequisites

- `git`, `python3`, `kicad-cli` (KiCad 10 or newer) and an authenticated GitHub CLI (`gh auth status`).
- Clean working tree (`git status --porcelain` is empty). Otherwise stop and ask the user.
- Current branch is the development branch `x.y.z_Dev` (e.g. `2.3.0_Dev`). Otherwise stop and tell the user.

## Project layout

All commands are run from the repository root.

| Parameter     | Value                   | Description                                                 |
| ------------- | ----------------------- | ----------------------------------------------------------- |
| `INPUT_DIR`   | `devkit`   | Directory with the KiCad project and the KiBot files        |
| `BOARD`       | `ZSWatch-Watch-DevKit`         | Base name of the `.kicad_pro` / `.kicad_sch` / `.kicad_pcb` |
| `MAIN_BRANCH` | `main`      | Main branch, receives the release                           |
| `DEV_BRANCH`  | `x.y.z_Dev`             | Current branch (`git branch --show-current`)                |
| `VERSION`     | `x.y.z`                 | Taken from `DEV_BRANCH`. Never ask for it or take it from elsewhere |

Files changed by this skill:

| File                                                             | Step |
| ---------------------------------------------------------------- | ---- |
| `devkit/*.kicad_sch` (page numbers and page links)    | 2    |
| `devkit/kibot_resources/templates/impedance_table.txt` | 3   |
| `devkit/ZSWatch-Watch-DevKit.kicad_pro` (unused net classes, only with approval) | 3 |
| `devkit/kibot_yaml/kibot_pre_set_text_variables.yaml` | 4    |
| `devkit/Revision History.kicad_sch`                   | 4    |
| `.github/workflows/hw-pcb.yaml`                                     | 5    |

Shell state is not kept between commands, so set the parameters again in every command that uses them:

```bash
INPUT_DIR='devkit'
BOARD='ZSWatch-Watch-DevKit'
MAIN_BRANCH='main'

DEV_BRANCH=$(git branch --show-current)
if [[ ! "$DEV_BRANCH" =~ ^([0-9]+\.[0-9]+\.[0-9]+)_Dev$ ]]; then
    echo "Branch '$DEV_BRANCH' is not a development branch x.y.z_Dev" >&2
    exit 1
fi
VERSION=${BASH_REMATCH[1]}
VERSION_RE=${VERSION//./\\.}
TEXT_VARS="$INPUT_DIR/kibot_yaml/kibot_pre_set_text_variables.yaml"
```

`VERSION` is used for the changelog variables (step 4), the commit message (step 6) and the tag (step 9).

## GitHub user

All pushes are done with the user that is logged in to the GitHub CLI, not with other credentials
stored for Git. `git_push` uses the token of the GitHub CLI for the push:

```bash
GH_USER=$(gh api user --jq .login)
git_push() {
    git -c credential.helper= -c credential.helper='!gh auth git-credential' push "$@"
}
```

Define both again in every command that pushes, and always push with `git_push` instead of `git push`.

Check before starting:

```bash
gh auth status
echo "GitHub user: $GH_USER"
git remote get-url origin
```

Abort if the GitHub CLI is not logged in. The token is only used for `https://` remotes. If `origin` is
an SSH remote (`git@github.com:...`), the SSH key decides which user pushes: tell the user and ask
before continuing. Show `GH_USER` in the summary before the first push.

## Checks before starting

The pipeline uses the names from the `env` section of `hw-pcb.yaml`, so they must match the parameters above:

```bash
grep -E '^  (kibot_input_dir|kicad_board|master_branch):' .github/workflows/hw-pcb.yaml
ls "$INPUT_DIR/$BOARD.kicad_pro" "$INPUT_DIR/$BOARD.kicad_sch" "$INPUT_DIR/$BOARD.kicad_pcb" "$TEXT_VARS"
```

If a name differs from `hw-pcb.yaml`, a file is missing or a name still looks like `${...}`
(the directory or the board was renamed, or the project was not initialized completely), do not guess.
Determine the real names (`git ls-files '*.kicad_pro'` gives `INPUT_DIR/BOARD.kicad_pro`,
`git branch -r` the main branch), show the user the difference and ask before continuing.

Abort if the tag already exists (`git ls-remote --tags origin "refs/tags/$VERSION"` returns a result)
or if `INPUT_DIR/CHANGELOG.md` has no entries in the `## [Unreleased]` section.

Show the user a short summary (version, development branch, main branch, GitHub user) and get a confirmation
before anything is pushed.

## Steps

Stop at the first failing step, report the error and do not continue.

### 1. Run ERC and DRC

```bash
cd "$INPUT_DIR"
mkdir -p /tmp/release-check
kicad-cli sch erc --severity-error --exit-code-violations \
    -o /tmp/release-check/erc.rpt "$BOARD.kicad_sch"
kicad-cli pcb drc --severity-error --schematic-parity --exit-code-violations \
    -o /tmp/release-check/drc.rpt "$BOARD.kicad_pcb"
cd -
```

A non-zero exit code means violations. Summarize the errors from the reports for the user and abort.
Warnings do not block the release.

### 2. Check the page numbers

After a sheet was added, removed or moved, the page numbers of the hierarchy can have gaps or duplicates,
and the page links on the sheets (e.g. a text "Page 7" with the link `#7` next to a sheet symbol) can point
to the wrong page. The sheet names of the table of contents and the outputs are read by page number, so
both must be correct before the release. [check_pages.py](check_pages.py) from this directory checks them:

```bash
CHECK_PAGES=.github/skills/create-release/check_pages.py
python3 "$CHECK_PAGES" "$INPUT_DIR/$BOARD.kicad_sch"
```

- Exit code `0`: page numbers and page links are correct, continue with step 3.
- Exit code `1`: the script lists every difference. Show the list to the user and ask before fixing it.
  The order of the current page numbers is kept, the pages are only numbered again without gaps.
  With the approval of the user fix them and check again:

  ```bash
  python3 "$CHECK_PAGES" "$INPUT_DIR/$BOARD.kicad_sch" --fix
  python3 "$CHECK_PAGES" "$INPUT_DIR/$BOARD.kicad_sch"
  git diff --stat
  ```

- Exit code `2`: the schematic can not be read, abort.

The schematic must not be open in KiCad while it is fixed (check for `*.lck` files in `INPUT_DIR`),
otherwise KiCad overwrites the fix when the user saves. Only the page numbers and the page links are
changed. The text variables `SHEET_NAME_<page>` of the table of contents follow the page numbers
automatically, they are read from the netlist XML by the pipeline.

### 3. Check the impedance table

The fabrication documents contain the impedance table from
`INPUT_DIR/kibot_resources/templates/impedance_table.txt` (header line plus one line per transmission line).
It must match the layout. The transmission lines with controlled impedance are the net classes named
`<Bus>_<Impedance>` (e.g. `USB_90`, `Ethernet_100`). Net classes without impedance (e.g. `GND`, `I2C`) are
ignored. [check_impedance.py](check_impedance.py) from this directory splits the names into bus and
impedance and takes the layer, the trace width, the gap and the reference layers from the layout:

```bash
CHECK_IMPEDANCE=.github/skills/create-release/check_impedance.py
IMPEDANCE_TABLE="$INPUT_DIR/kibot_resources/templates/impedance_table.txt"
python3 "$CHECK_IMPEDANCE" "$INPUT_DIR/$BOARD.kicad_pro" "$IMPEDANCE_TABLE"
```

The script prints the expected rows, the rows of the table and the problems. Exit code `0` means the
table matches, continue with step 4. Exit code `2` means the input can not be read, abort. With exit
code `1` go through the problems with the user. Ask instead of guessing, collect the questions and ask
them together:

| Problem                                   | Question to the user                                          |
| ----------------------------------------- | ------------------------------------------------------------- |
| Unknown tolerance (`?`)                   | Impedance tolerance in percent (usually 10)                   |
| Unknown reference layers (`?`)            | Reference layer(s) of the line (no ground zone next to it)    |
| Net class without routed tracks           | Remove the net class from the project or keep it out of the table |
| Tracks with another width than the class  | Fix the layout or the net class (the user decides, do not change the layout) |

Then write the table with the answers and check again:

```bash
python3 "$CHECK_IMPEDANCE" "$INPUT_DIR/$BOARD.kicad_pro" "$IMPEDANCE_TABLE" --tolerance <percent> --write
python3 "$CHECK_IMPEDANCE" "$INPUT_DIR/$BOARD.kicad_pro" "$IMPEDANCE_TABLE"
```

`--tolerance` is only needed when a row has no tolerance yet, existing tolerances are kept. A net class
is only removed from `BOARD.kicad_pro` (entry in `net_settings.classes` and its `netclass_patterns`) with
the approval of the user and while KiCad is closed (no `*.lck` files in `INPUT_DIR`). Do not continue
before the check returns `0`.

### 4. Set the version of the changelog variables

The changelog of a version is written into the text variables `RELEASE_TITLE_<version>` and
`RELEASE_BODY_<version>` by the KiBot preflight `set_text_variables`. The table on the revision history
sheet of the schematic shows them via `${RELEASE_TITLE_<version>}` and `${RELEASE_BODY_<version>}`.

Free entries for the next release use the placeholder version `x.y.z`:

- KiBot (`TEXT_VARS`):

  ```yaml
      - variable: '@RELEASE_TITLE_VAR@x.y.z'
        command: '@GET_TITLE_CMD@ x.y.z'
      - variable: '@RELEASE_BODY_VAR@x.y.z'
        command: '@GET_BODY_CMD@ x.y.z'
  ```

- Schematic (revision history sheet): `${RELEASE_TITLE_x.y.z}` and `${RELEASE_BODY_x.y.z}`

This step sets both to `VERSION`, the version from the branch name (e.g. `x.y.z` becomes `1.2.0`).
Entries of earlier versions stay untouched.

```bash
# Schematic sheet with the revision history table
REV_SHEET=$(git grep -l -F '${RELEASE_TITLE_' -- "$INPUT_DIR/*.kicad_sch")
```

Abort and ask the user if `REV_SHEET` is not exactly one file.

Before changing anything, check both files:

```bash
# Entries for VERSION already present (KiBot: active lines only)
grep -cE "^\s*- variable: '@RELEASE_(TITLE|BODY)_VAR@${VERSION_RE}'" "$TEXT_VARS"
grep -cE "\\$\{RELEASE_(TITLE|BODY)_${VERSION_RE}\}" "$REV_SHEET"
# Free entries (KiBot: active or commented)
grep -cE "^\s*(#\s*)?- variable: '@RELEASE_TITLE_VAR@x\.y\.z'" "$TEXT_VARS"
grep -cF '${RELEASE_TITLE_x.y.z}' "$REV_SHEET"
```

A file that already has the entries for `VERSION` stays unchanged. A file without them needs a free
`x.y.z` entry. If one is missing, stop without changing any file, show the user the versions used
(`grep -oE "@RELEASE_TITLE_VAR@[^']+" "$TEXT_VARS"` and `grep -oE '\$\{RELEASE_TITLE_[^}]+\}' "$REV_SHEET"`)
and ask how to continue.

**KiBot:** If `TEXT_VARS` has no entry for `VERSION` yet, set the first free `x.y.z` block to `VERSION`.
An active block is preferred. If there is only the commented example, it is uncommented, otherwise KiBot
would not run it. The `UNRELEASED` entries stay untouched.

```bash
python3 - "$TEXT_VARS" "$VERSION" <<'EOF'
import re
import sys

path, version = sys.argv[1], sys.argv[2]
with open(path, encoding="utf-8", newline="") as f:
    lines = f.read().splitlines(keepends=True)

# The four lines of a free entry, each optionally commented out
block = [r"- variable: '@RELEASE_TITLE_VAR@x\.y\.z'", r"  command: '@GET_TITLE_CMD@ x\.y\.z'",
         r"- variable: '@RELEASE_BODY_VAR@x\.y\.z'", r"  command: '@GET_BODY_CMD@ x\.y\.z'"]
pattern = [re.compile(r"^(\s*)(# ?)?(%s)(\s*)$" % b) for b in block]

starts = [i for i in range(len(lines) - 3)
          if all(pattern[k].match(lines[i + k]) for k in range(4))]
if not starts:
    sys.exit("No free x.y.z entry in %s" % path)
# Prefer an active block over the commented example
active = [i for i in starts if not pattern[0].match(lines[i]).group(2)]
start = (active or starts)[0]

for k in range(4):
    m = pattern[k].match(lines[start + k])
    lines[start + k] = m.group(1) + m.group(3).replace("x.y.z", version) + m.group(4)

with open(path, "w", encoding="utf-8", newline="") as f:
    f.write("".join(lines))
EOF
```

**Schematic:** If `REV_SHEET` has no entry for `VERSION` yet, fill the first free entry: replace
`${RELEASE_TITLE_x.y.z}` with `${RELEASE_TITLE_<VERSION>}` and `${RELEASE_BODY_x.y.z}` with
`${RELEASE_BODY_<VERSION>}` (e.g. `${RELEASE_TITLE_1.2.0}`). With several free entries only the
leftmost one (then topmost) is filled, the others stay free for later releases:

```bash
python3 - "$REV_SHEET" "$VERSION" <<'EOF'
import re
import sys

path, version = sys.argv[1], sys.argv[2]
with open(path, encoding="utf-8", newline="") as f:
    text = f.read()

for kind in ("TITLE", "BODY"):
    placeholder = "${RELEASE_%s_x.y.z}" % kind
    # Position of every text box with the placeholder: (text_box "..." ... (at X Y ...)
    boxes = re.finditer(
        r'\(text_box "%s"(?:(?!\(text_box ).)*?\(at ([-\d.]+) ([-\d.]+)' % re.escape(placeholder),
        text, re.S)
    first = min(boxes, key=lambda m: (float(m.group(1)), float(m.group(2))), default=None)
    if first is None:
        sys.exit("No free entry %s in %s" % (placeholder, path))
    pos = first.start() + len('(text_box "')
    text = text[:pos] + "${RELEASE_%s_%s}" % (kind, version) + text[pos + len(placeholder):]

with open(path, "w", encoding="utf-8", newline="") as f:
    f.write(text)
EOF
```

Verify the result. KiBot and the schematic must use the same names, the schematic each exactly once:

```bash
grep -E "^\s*(- variable|  command): '@(RELEASE_(TITLE|BODY)_VAR@|GET_(TITLE|BODY)_CMD@ )${VERSION_RE}'" "$TEXT_VARS"
grep -oE "\\$\{RELEASE_(TITLE|BODY)_${VERSION_RE}\}" "$REV_SHEET"
git diff --stat
```

Only change these values, keep the rest of the files untouched.

### 5. Set the variant to CHECKED

In `.github/workflows/hw-pcb.yaml` set `  kibot_variant: <OLD>` to `  kibot_variant: CHECKED`.
Only change this value, keep the rest of the file untouched.

### 6. Commit and push to the development branch

The commit message uses the version determined from the branch name, e.g. `Prepare Release 2.3.0` on `2.3.0_Dev`.

```bash
# Working tree was clean before, so this only stages the changes of steps 2 to 5
git add -u
git diff --cached --stat
git commit -m "Prepare Release $VERSION"
# After the commit, 'git pull --rebase' refuses to run with uncommitted changes
git pull --rebase origin "$DEV_BRANCH"
git_push origin "$DEV_BRANCH"
```

### 7. Wait for the KiBot pipeline

```bash
SHA=$(git rev-parse HEAD)
# The run may need a few seconds to show up, retry until it exists
RUN_ID=$(gh run list --workflow hw-pcb.yaml --branch "$DEV_BRANCH" --commit "$SHA" \
    --json databaseId --jq '.[0].databaseId')
gh run watch "$RUN_ID" --exit-status
```

On failure show the failed jobs (`gh run view "$RUN_ID" --log-failed | tail -n 100`) and abort.

### 8. Pull the netlist XML, switch to the main branch and merge the development branch

The pipeline pushes the generated netlist XML (`INPUT_DIR/BOARD.xml`) back to the development branch.
The release pipeline reads the sheet titles from it, so pull it before merging. The other outputs are
only uploaded as workflow artifact.

```bash
git pull --rebase origin "$DEV_BRANCH"
ls "$INPUT_DIR/$BOARD.xml"
git checkout "$MAIN_BRANCH"
git pull origin "$MAIN_BRANCH"
git pull --no-rebase --no-edit origin "$DEV_BRANCH"
```

On merge conflicts stop and hand over to the user.

### 9. Create the tag

The tag is the version determined from the branch name, e.g. tag `2.3.0` on `2.3.0_Dev`. It must match
the version used in step 4 and in the commit message of step 6.

```bash
git tag "$VERSION"
```

### 10. Push the main branch and the tag

```bash
git_push --atomic origin "$MAIN_BRANCH" "$VERSION"
```

### 11. Wait for the release pipeline

The push of the tag starts the run that builds the release. The push of the main branch starts no run,
`hw-pcb.yaml` is not triggered by the main branch. Only the tag run decides whether the release was
successful.

```bash
SHA=$(git rev-parse HEAD)
# The runs may need a few seconds to show up, retry until the tag run exists
gh run list --workflow hw-pcb.yaml --commit "$SHA" --json databaseId,headBranch,status
# Run of the tag: headBranch is the version
TAG_RUN_ID=$(gh run list --workflow hw-pcb.yaml --commit "$SHA" --json databaseId,headBranch \
    --jq ".[] | select(.headBranch == \"$VERSION\") | .databaseId")
gh run watch "$TAG_RUN_ID" --exit-status
```

If the tag run fails, show the failed log (`gh run view "$TAG_RUN_ID" --log-failed | tail -n 100`) and abort.
Never delete or move the tag without asking the user.

If the tag run succeeds, the release is done. If the list shows other runs of this commit (projects with
an older workflow also build the main branch), wait for them as well (`gh run watch <RUN_ID> --exit-status`).
A failure of such a run does not fail the release: report it as a warning with the failed step
(`gh run view <RUN_ID> --log-failed | tail -n 30`) and continue.

Report the release URL (`gh release view "$VERSION" --json url --jq .url`).

### 12. Pull the release state

The release pipeline pushes the updated `CHANGELOG.md` and the release outputs to the main branch.
Pull them, so the local main branch has the released state:

```bash
git checkout "$MAIN_BRANCH"
git pull --ff-only origin "$MAIN_BRANCH"
git log --oneline -n 5
```

`MAIN_BRANCH` is the branch from `master_branch` in `hw-pcb.yaml` (`main` or `master`).

### 13. Check out the main branch

The release ends with the main branch checked out, so the working copy shows the released state and no further
work lands on the old development branch by accident. Do this as the last action, also when step 12 fails
(e.g. because of local changes) or a run of the main branch failed in step 11:

```bash
git checkout "$MAIN_BRANCH"
test "$(git branch --show-current)" = "$MAIN_BRANCH"
git status -sb
```

If the checkout fails, report the error and the current branch to the user. Report the checked out branch in the
summary.
