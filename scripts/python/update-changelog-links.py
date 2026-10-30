"""
update-changelog-links.py - Manage the 'Full Changelog' comparison link block
in CHANGELOG.md.

Usage:
    python update-changelog-links.py -f CHANGELOG.md -t <tag> [-p <prev-tag>] -r <repo-url>

Arguments:
    -f, --file      Path to the CHANGELOG.md file.
    -t, --tag       Current release tag (e.g. v2.0.0).
    -p, --prev-tag  Previous release tag (e.g. v1.0.0). Omit for the first release.
    -r, --repo-url  Base URL of the GitHub repository without trailing slash
                    (e.g. https://github.com/owner/repo).

Description:
    Appends or updates the '**Full Changelog**:' block at the end of the
    CHANGELOG.md file with a GitHub compare URL between the previous and the
    current release tag.

    Behaviour per release:
    - First release (no prev-tag): no link is added.
    - Second release: appends the block with one compare URL.
    - Subsequent releases: prepends the new compare URL and keeps all
      previous URLs below it in chronological-descending order.

    This script is typically called from the GitHub Actions release workflow
    (hw-pcb.yaml) after a version tag is pushed.

Example output block in CHANGELOG.md:
    **Full Changelog**:
    https://github.com/owner/repo/compare/v1.0.0...v2.0.0
    https://github.com/owner/repo/compare/v0.1.0...v1.0.0
"""

import re
import sys
import argparse

MARKER = "**Full Changelog**:"

def update_changelog_links(file_path, current_tag, prev_tag, repo_url):
    """
    Appends or updates the **Full Changelog** link block at the end of the
    CHANGELOG.md file.

    Rules:
    - First release (no prev_tag): nothing is added.
    - Second release: adds "**Full Changelog**: <compare_url>" at the end.
    - Subsequent releases: prepends the new compare URL as the lead line and
      demotes the previous lead URL to a plain URL below it.

    Example after third release:
        **Full Changelog**:
        https://github.com/owner/repo/compare/2.0...3.0
        https://github.com/owner/repo/compare/1.0...2.0

    (The marker line contains no inline URL; all URLs follow on separate lines.)
    """
    if not prev_tag:
        print(f"First release ({current_tag}), no Full Changelog link added.")
        return

    new_url = f"{repo_url}/compare/{prev_tag}...{current_tag}"

    try:
        with open(file_path, "r") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.", file=sys.stderr)
        sys.exit(1)

    stripped = content.rstrip("\n")

    # Check whether a Full Changelog block already exists at the end
    # The block starts with "**Full Changelog**:" and contains one or more lines
    block_pattern = re.compile(
        r"\n\n(\*\*Full Changelog\*\*:.*?)$",
        re.DOTALL
    )
    match = block_pattern.search(stripped)

    if match:
        existing_block = match.group(1)

        # Extract all URLs from the existing block:
        # First line: "**Full Changelog**: URL"  -> extract URL
        # Remaining lines: plain URLs
        lines = existing_block.splitlines()
        old_urls = []

        for line in lines:
            stripped_line = line.strip()
            # Skip the marker line itself and empty lines
            if stripped_line and not stripped_line == MARKER:
                # Handle old inline format: "**Full Changelog**: <url>"
                if stripped_line.startswith(MARKER):
                    url = stripped_line[len(MARKER):].strip()
                    if url:
                        old_urls.append(url)
                else:
                    old_urls.append(stripped_line)

        # Build new block: marker on its own line, new URL first, then old URLs
        new_block_lines = [MARKER, new_url]
        for url in old_urls:
            new_block_lines.append(url)

        new_block = "\n".join(new_block_lines)
        new_content = stripped[: match.start()] + "\n\n" + new_block + "\n"
    else:
        # No existing block: simply append the new entry
        new_block = f"{MARKER}\n{new_url}"
        new_content = stripped + "\n\n" + new_block + "\n"

    with open(file_path, "w") as f:
        f.write(new_content)

    print(f"Full Changelog link updated: {new_url}")

if(__name__ == "__main__"):
    parser = argparse.ArgumentParser(
        description="Add or update the **Full Changelog** link block at the end of CHANGELOG.md."
    )
    parser.add_argument("-f", "--file", required=True, help="Path to the CHANGELOG.md file.")
    parser.add_argument("-t", "--tag", required=True, help="Current release tag.")
    parser.add_argument("-p", "--prev-tag", default="", help="Previous release tag (empty for first release).")
    parser.add_argument("-r", "--repo-url", required=True, help="Base URL of the GitHub repository (without trailing slash).")
    args = parser.parse_args()

    update_changelog_links(args.file, args.tag, args.prev_tag, args.repo_url)
