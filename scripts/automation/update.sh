#!/bin/zsh -l
# Monthly update: newest code, new Statcast pitches for the current season, slim copies, edge engine.
# Run by the LaunchAgent on the 1st of each month at 6:00 AM, or by hand: ~/Baseball/scripts/automation/update.sh
set -u
REPO="$HOME/Baseball"
LOG_DIR="$REPO/data/logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/update-$(date +%Y-%m-%d).log"
exec > >(tee -a "$LOG") 2>&1

echo "=== Baseball update $(date) ==="
cd "$REPO" || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

YEAR=$(date +%Y)
MONTH=$(date +%m); MONTH=${MONTH#0}
SEASON=$YEAR
[ "$MONTH" -lt 3 ] && SEASON=$((YEAR - 1))       # Jan-Feb belong to last season

git pull --ff-only || echo "git pull skipped (local changes?)"
uv sync --quiet

for S in $((SEASON - 2)) $((SEASON - 1)); do      # earlier seasons: only fill gaps
  caffeinate -i uv run bb pull-league "$S" && uv run bb slim "$S"
done
caffeinate -i uv run bb pull-league "$SEASON" --refresh-recent && uv run bb slim "$SEASON"
caffeinate -i uv run bb edge "$SEASON" && uv run bb board "$SEASON"

echo "=== Done $(date) ==="
