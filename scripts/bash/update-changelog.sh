#!/bin/bash
#
# update-changelog.sh - Git commit-msg hook for automatic CHANGELOG.md updates
#
# Usage:
#   Called automatically by Git as a commit-msg hook.
#   Copy or symlink this script to .git/hooks/commit-msg.
#
# Commit message format:
#   <Category>: <Message>
#
#   Closes: #<issue-number>
#
# Supported categories:
#   Added    - New features or capabilities
#   Changed  - Changes to existing functionality
#   Fixed    - Bug fixes
#   Removed  - Removed features or files
#
# The script reads the commit message file passed by Git, extracts the category,
# message, and optional issue reference, and inserts a formatted entry under the
# matching section in CHANGELOG.md. If the section does not yet exist it is
# created automatically.
#
# Example commit message:
#   Added: Support for 4-layer PCB templates
#
#   Closes: #42

COMMIT_MSG_FILE=$1
CHANGELOG="CHANGELOG.md"

# Read first line (Category: Message)
HEADER=$(head -n 1 "$COMMIT_MSG_FILE")

CATEGORY=$(echo "$HEADER" | cut -d':' -f1)
MESSAGE=$(echo "$HEADER" | cut -d':' -f2- | xargs)

# Extract issue (Closes: #123)
ISSUE=$(grep -i "Closes:" "$COMMIT_MSG_FILE" | grep -oE "#[0-9]+")

# Validate category
case "$CATEGORY" in
  Added|Fixed|Changed|Removed)
    ;;
  *)
    echo "Invalid category: $CATEGORY"
    exit 0
    ;;
esac

# Format entry
ENTRY="- $MESSAGE ($ISSUE)"

# Create section if it doesn't exist
if ! grep -q "## $CATEGORY" "$CHANGELOG"; then
  echo -e "\n## $CATEGORY:\n" >> "$CHANGELOG"
fi

# Insert entry under the correct category
awk -v category="## $CATEGORY" -v entry="$ENTRY" '
  $0 == category {
    print;
    getline;
    print;
    print entry;
    next;
  }
  { print }
' "$CHANGELOG" > tmp_changelog && mv tmp_changelog "$CHANGELOG"