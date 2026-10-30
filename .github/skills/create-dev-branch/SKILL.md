---
name: create-dev-branch
description: Create the development branch x.y.z_Dev for the next hardware release of this KiCad project. Asks for the version, pulls the main branch, creates the branch, removes the production data of the previous release, sets the KiBot variant to PRELIMINARY, adds a free x.y.z entry for the changelog variables to the KiBot configuration and the schematic, commits "Prepare Development Branch for Release x.y.z" and pushes the branch. Use when the user asks to create or prepare a development branch or to start the work on a new version.
---

# Create Development Branch

Prepares a development branch from any state of the main branch. After this skill only the design work
and the entries in the `CHANGELOG.md` are missing, then the release is created with the
[create-release](../create-release/SKILL.md) skill.

The skill leaves the branch in the state `create-release` expects:

- Branch `x.y.z_Dev`, pushed to `origin`
- A free `x.y.z` entry for the changelog variables in the KiBot configuration and in the schematic
- `kibot_variant: PRELIMINARY` in [hw-pcb.yaml](../../workflows/hw-pcb.yaml)

## Prerequisites

- `git`, `python3` and an authenticated GitHub CLI (`gh auth status`).
- Clean working tree (`git status --porcelain` is empty). Otherwise stop and ask the user.

## Project layout

All commands are run from the repository root.

| Parameter     | Value                   | Description                                                 |
| ------------- | ----------------------- | ----------------------------------------------------------- |
| `INPUT_DIR`   | `devkit`   | Directory with the KiCad project and the KiBot files        |
| `BOARD`       | `ZSWatch-Watch-DevKit`         | Base name of the `.kicad_pro` / `.kicad_sch` / `.kicad_pcb` |
| `MAIN_BRANCH` | `main`      | Main branch, the development branch starts here             |
| `VERSION`     | `x.y.z`                 | Version of the next release, entered by the user (step 1)   |
| `DEV_BRANCH`  | `x.y.z_Dev`             | `VERSION` followed by `_Dev`                                |

Files changed by this skill:

| File                                                             | Step |
| ---------------------------------------------------------------- | ---- |
| Production directory (`kibot_output_path` in `hw-pcb.yaml`)         | 4    |
| `.github/workflows/hw-pcb.yaml`                                     | 5    |
| `devkit/kibot_yaml/kibot_pre_set_text_variables.yaml` | 6    |
| `devkit/Revision History.kicad_sch`                   | 6    |

Shell state is not kept between commands, so set the parameters again in every command that uses them:

```bash
INPUT_DIR='devkit'
BOARD='ZSWatch-Watch-DevKit'
MAIN_BRANCH='main'
TEXT_VARS="$INPUT_DIR/kibot_yaml/kibot_pre_set_text_variables.yaml"
```

From step 3 on the version is taken from the branch name, the same way `create-release` does it:

```bash
DEV_BRANCH=$(git branch --show-current)
if [[ ! "$DEV_BRANCH" =~ ^([0-9]+\.[0-9]+\.[0-9]+)_Dev$ ]]; then
    echo "Branch '$DEV_BRANCH' is not a development branch x.y.z_Dev" >&2
    exit 1
fi
VERSION=${BASH_REMATCH[1]}
```

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

## Steps

Stop at the first failing step, report the error and do not continue.

### 1. Ask for the version

Ask the user for the version of the next release. Always ask, never derive it from tags or branches.

The version is extended to three parts `x.y.z`: `2` becomes `2.0.0`, `1.3` becomes `1.3.0`, `1.3.1` stays.
Everything else (`v1.3`, `1.3.0-rc1`, `1.3.0_Dev`, four parts) is rejected, ask again.

```bash
INPUT='<answer of the user>'
if [[ ! "$INPUT" =~ ^([0-9]+)(\.([0-9]+))?(\.([0-9]+))?$ ]]; then
    echo "'$INPUT' is not a version x, x.y or x.y.z" >&2
    exit 1
fi
# 10# removes leading zeros
VERSION="$((10#${BASH_REMATCH[1]})).$((10#${BASH_REMATCH[3]:-0})).$((10#${BASH_REMATCH[5]:-0}))"
DEV_BRANCH="${VERSION}_Dev"

git fetch origin --tags --prune
# Tag or branch already exists
git ls-remote --tags origin "refs/tags/$VERSION"
git tag -l "$VERSION"
git branch -a --list "$DEV_BRANCH" "origin/$DEV_BRANCH"
# Newest release
git tag -l | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' | sort -V | tail -n 1
```

Abort if the tag or the branch already exists. If the version is not higher than the newest release,
show both versions and ask the user whether this is intended (e.g. a patch for an older release).

From here on `x.y.z` in the branch name and in the commit message means this version. In the changelog
variables (step 6) `x.y.z` stays the literal placeholder, `create-release` replaces it with the version.

### 2. Pull the main branch

```bash
git checkout "$MAIN_BRANCH"
git pull --ff-only origin "$MAIN_BRANCH"
```

The release pipeline pushes the updated `CHANGELOG.md` to the main branch, so the pull is required
even directly after a release.

### 3. Create the development branch

```bash
git checkout -b "$DEV_BRANCH"
```

All following changes are made on the development branch, the main branch stays untouched.

### 4. Remove the production data of the previous release

The KiBot outputs are written to `kibot_output_dir/kibot_output_path` of `hw-pcb.yaml`
(`../production` relative to `INPUT_DIR` is `production` in the repository root).

```bash
OUT_DIR=$(sed -n 's/^  kibot_output_dir: *//p' .github/workflows/hw-pcb.yaml)
OUT_PATH=$(sed -n 's/^  kibot_output_path: *//p' .github/workflows/hw-pcb.yaml)
PROD_DIR=$(realpath -m --relative-to=. "$OUT_DIR/$OUT_PATH")
echo "Production directory: $PROD_DIR"
# Other directories with production data
find . -maxdepth 2 -type d -name production -not -path './.git/*'
```

`PROD_DIR` must be a subdirectory of the repository: abort if it is empty, `.`, starts with `..` or `/`,
or is `INPUT_DIR` itself. Then remove it from the repository (if it is tracked) and from the disk:

```bash
git rm -r -q --ignore-unmatch -- "$PROD_DIR"
rm -rf -- "$PROD_DIR"
```

If `find` lists another `production` directory, ask the user before removing it.

The netlist XML (`INPUT_DIR/BOARD.xml`) is kept. KiBot reads the sheet titles for the table of contents
from it and the pipeline replaces it with the first build of the branch.

### 5. Set the variant to PRELIMINARY

```bash
sed -i 's/^  kibot_variant: .*/  kibot_variant: PRELIMINARY/' .github/workflows/hw-pcb.yaml
grep -n '^  kibot_variant:' .github/workflows/hw-pcb.yaml
```

The `grep` must show exactly one line `  kibot_variant: PRELIMINARY`.
Only change this value, keep the rest of the file untouched.

### 6. Add a free entry for the changelog variables

The changelog of a version is written into the text variables `RELEASE_TITLE_<version>` and
`RELEASE_BODY_<version>` by the KiBot preflight `set_text_variables`. The table on the revision history
sheet of the schematic shows them via `${RELEASE_TITLE_<version>}` and `${RELEASE_BODY_<version>}`.

`create-release` needs a free entry with the placeholder version `x.y.z` in both files:

- KiBot (`TEXT_VARS`):

  ```yaml
      - variable: '@RELEASE_TITLE_VAR@x.y.z'
        command: '@GET_TITLE_CMD@ x.y.z'
      - variable: '@RELEASE_BODY_VAR@x.y.z'
        command: '@GET_BODY_CMD@ x.y.z'
  ```

- Schematic (revision history sheet): `${RELEASE_TITLE_x.y.z}` and `${RELEASE_BODY_x.y.z}`

The columns of the table contain a released version (`${RELEASE_TITLE_1.2.0}`), the free entry
(`${RELEASE_TITLE_x.y.z}`) or are unused (`${RELEASE_TITLE_...}`). The free entry is created like this:

| State of the table                  | Schematic                                                             | KiBot                                              |
| ----------------------------------- | --------------------------------------------------------------------- | -------------------------------------------------- |
| Free `x.y.z` column exists          | Unchanged                                                             | Free block is added if it is missing               |
| Unused `...` columns exist          | The unused column following the newest release becomes `x.y.z`        | Free block is added                                |
| All columns show a released version | The column of the oldest release becomes `x.y.z`                      | Block of the oldest release is removed, free block is added |

The entries of all releases that are still shown in the table stay untouched in both files.
The `UNRELEASED` entries stay untouched.

```bash
# Schematic sheet with the revision history table
REV_SHEET=$(git grep -l -F '${RELEASE_TITLE_' -- "$INPUT_DIR/*.kicad_sch")
```

Abort and ask the user if `REV_SHEET` is not exactly one file.

The script checks both files first and writes them only if everything is consistent. On an error no
file is changed, show the user the entries (`grep -oE "@RELEASE_TITLE_VAR@[^']+" "$TEXT_VARS"` and
`grep -oE '\$\{RELEASE_(TITLE|BODY)_[^}]+\}' "$REV_SHEET"`) and ask how to continue.

```bash
python3 - "$TEXT_VARS" "$REV_SHEET" <<'EOF'
import re
import sys

text_vars, rev_sheet = sys.argv[1], sys.argv[2]
FREE, UNUSED = "x.y.z", "..."


def read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


def version_key(version):
    return tuple(int(part) for part in version.split("."))


# --- Schematic: columns of the revision history table, from left to right
sch = read(rev_sheet)
boxes = {"TITLE": [], "BODY": []}
for m in re.finditer(
        r'\(text_box "\$\{RELEASE_(TITLE|BODY)_([^}"]+)\}"(?:(?!\(text_box ).)*?\(at ([-\d.]+) ([-\d.]+)',
        sch, re.S):
    boxes[m.group(1)].append((float(m.group(3)), float(m.group(4)), m.group(2), m.start(2), m.end(2)))
titles, bodies = sorted(boxes["TITLE"]), sorted(boxes["BODY"])
if not titles or len(titles) != len(bodies):
    sys.exit("%s: %d title and %d body entries, expected the same number (at least one)"
             % (rev_sheet, len(titles), len(bodies)))
names = [t[2] for t in titles]
if names != [b[2] for b in bodies]:
    sys.exit("%s: title and body entries do not match: %s / %s" % (rev_sheet, names, [b[2] for b in bodies]))
unknown = [n for n in names if n not in (FREE, UNUSED) and not re.fullmatch(r"\d+\.\d+\.\d+", n)]
if unknown:
    sys.exit("%s: unexpected entries %s" % (rev_sheet, unknown))
released = [n for n in names if n not in (FREE, UNUSED)]

dropped = None
if FREE in names:
    column = None
elif UNUSED in names:
    # The unused column following the newest release, otherwise the leftmost unused one
    unused = [i for i, n in enumerate(names) if n == UNUSED]
    newest = names.index(max(released, key=version_key)) if released else -1
    column = next((i for i in unused if i > newest), unused[0])
else:
    # Table is full: the oldest release makes room
    dropped = min(released, key=version_key)
    column = names.index(dropped)

if column is not None:
    # Replace from the back, so the positions of the first match stay valid
    for _, _, _, start, end in sorted((titles[column], bodies[column]), key=lambda b: -b[3]):
        sch = sch[:start] + FREE + sch[end:]
    released = [n for n in released if n != dropped]

# --- KiBot: one block of four lines per version
lines = read(text_vars).splitlines(keepends=True)
BLOCK = [r"- variable: '@RELEASE_TITLE_VAR@%s'", r"  command: '@GET_TITLE_CMD@ %s'",
         r"- variable: '@RELEASE_BODY_VAR@%s'", r"  command: '@GET_BODY_CMD@ %s'"]


def find_blocks(version):
    """Start lines of all blocks of a version. Each line may be commented out."""
    pattern = [re.compile(r"^(\s*)(# ?)?(%s)(\s*)$" % (b % version)) for b in BLOCK]
    return [(i, pattern) for i in range(len(lines) - 3)
            if all(pattern[k].match(lines[i + k]) for k in range(4))]


def is_active(block):
    return not block[1][0].match(lines[block[0]]).group(2)


if dropped:
    for start, _ in reversed(find_blocks(re.escape(dropped))):
        end = start + 4
        if end < len(lines) and not lines[end].strip():
            end += 1
        del lines[start:end]

free_blocks = find_blocks(re.escape(FREE))
if not any(is_active(b) for b in free_blocks):
    if free_blocks:
        # Only the commented example exists: uncomment it
        start, pattern = free_blocks[0]
        for k in range(4):
            m = pattern[k].match(lines[start + k])
            lines[start + k] = m.group(1) + m.group(3) + m.group(4)
    else:
        # New block in front of the UNRELEASED entries, otherwise behind the last release
        anchor = find_blocks("UNRELEASED")
        if anchor:
            pos = anchor[0][0]
            ref = lines[pos]
        else:
            body = [i for i, line in enumerate(lines)
                    if re.match(r"^\s*  command: '@GET_BODY_CMD@ \d+\.\d+\.\d+'\s*$", line)]
            if not body:
                sys.exit("%s: no position for the new x.y.z entry found" % text_vars)
            pos = body[-1] + 1
            ref = lines[body[-1] - 3]
        indent = re.match(r"^(\s*)", ref).group(1)
        eol = "\r\n" if ref.endswith("\r\n") else "\n"
        new = [indent + (b % FREE) + eol for b in BLOCK]
        lines[pos:pos] = new + [eol] if anchor else [eol] + new

active = set()
for line in lines:
    m = re.match(r"^\s*- variable: '@RELEASE_TITLE_VAR@(\d+\.\d+\.\d+)'\s*$", line)
    if m:
        active.add(m.group(1))

# --- Write both files only after everything was resolved
with open(rev_sheet, "w", encoding="utf-8", newline="") as f:
    f.write(sch)
with open(text_vars, "w", encoding="utf-8", newline="") as f:
    f.write("".join(lines))

if dropped:
    print("Removed the oldest release %s from the revision history" % dropped)
for version in sorted(set(released) - active, key=version_key):
    print("WARNING: %s is shown in the schematic, but has no KiBot entry" % version)
for version in sorted(active - set(released), key=version_key):
    print("WARNING: %s has a KiBot entry, but is not shown in the schematic" % version)
EOF
```

Show the user the warnings of the script, they do not stop the skill.

Verify the result. Both files must contain the free entry, the schematic each exactly once:

```bash
grep -E "^\s*(- variable|  command): '@(RELEASE_(TITLE|BODY)_VAR@|GET_(TITLE|BODY)_CMD@ )x\.y\.z'" "$TEXT_VARS"
grep -oE '\$\{RELEASE_(TITLE|BODY)_[^}]+\}' "$REV_SHEET"
git diff --stat
```

Only change these values, keep the rest of the files untouched.

### 7. Check the changelog

```bash
grep -n '^## \[Unreleased\]' "$INPUT_DIR/CHANGELOG.md"
```

If the `## [Unreleased]` section is missing, stop and ask the user. Do not add entries to the section,
they are written by the user during the design work.

### 8. Commit

The commit message uses the version from step 1, e.g. `Prepare Development Branch for Release 1.3.0`.

```bash
# Working tree was clean before, so this only stages the changes of steps 4 to 6
git add -u
git diff --cached --stat
git commit --allow-empty -m "Prepare Development Branch for Release $VERSION"
```

`--allow-empty` creates the commit also if the main branch was already prepared (new project).

### 9. Push the development branch

Show the user a short summary (version, development branch, main branch, GitHub user, changed files, removed
release from the revision history) and get a confirmation before the branch is pushed.

```bash
git_push -u origin "$DEV_BRANCH"
```

`create-release` pulls the development branch from `origin`, so the release fails without this push.
If the user declines, tell them to push the branch before the release.

If the commit changed the hardware directory or `hw-pcb.yaml`, the push starts the `Hardware / PCB Data` workflow
with the `PRELIMINARY` variant. It pushes the generated netlist XML back to the development branch.

### 10. Report the next steps

1. Pull the branch after the pipeline run, if one was started (`git pull --rebase origin "$DEV_BRANCH"`)
2. Do the design work and document all changes in the `## [Unreleased]` section of `INPUT_DIR/CHANGELOG.md`
3. Create the release with the `create-release` skill
