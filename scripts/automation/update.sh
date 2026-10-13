#!/bin/zsh -l
# Monthly update: newest code, new Statcast pitches for the current season, slim and sequence copies, edge engine,
# familiarity study.
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

NOREPLY="196597359+IForSureI@users.noreply.github.com"   # GitHub no-reply address: commits never carry the personal email
git config user.name "Dylan Fanelli"; git config user.email "$NOREPLY"
git pull --ff-only || echo "git pull skipped (local changes?)"
uv sync --quiet
uv run bb people || echo "people register refresh skipped"

for S in $((SEASON - 2)) $((SEASON - 1)); do      # earlier seasons: only fill gaps
  caffeinate -i uv run bb pull-league "$S" && uv run bb slim "$S" && uv run bb seq "$S"
done
caffeinate -i uv run bb pull-league "$SEASON" --refresh-recent && uv run bb slim "$SEASON" && uv run bb seq "$SEASON"
caffeinate -i uv run bb edge "$SEASON" && uv run bb board "$SEASON"
caffeinate -i uv run bb familiarity "$SEASON"      # pitch-type familiarity study + page (data/edge/familiarity/)
caffeinate -i uv run bb levers "$SEASON"           # pitch-design levers (data/edge/levers/; reports keep reviewed snapshots)
caffeinate -i uv run bb hook "$SEASON"             # exposure-aware hook (data/edge/hook/)

PRIVATE="$HOME/Baseball-private"
if [ -d "$PRIVATE/.git" ]; then
  echo "--- Private repo: pull, process inbox, commit ---"
  cd "$PRIVATE" && git config user.name "Dylan Fanelli" && git config user.email "$NOREPLY"
  git pull --ff-only && uv sync --quiet && uv run bbp ingest
  git add -A && (git diff --cached --quiet || git commit -qm "Monthly update: inbox processed $(date +%Y-%m-%d)") && git push -q
  cd "$REPO"
fi

echo "=== Done $(date) ==="
