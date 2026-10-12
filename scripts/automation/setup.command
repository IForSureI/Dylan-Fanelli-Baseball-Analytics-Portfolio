#!/bin/zsh -l
# One-time setup, launched by double-clicking in Finder:
#   1. private repo for team data and scouting notes (IForSureI/Baseball-private, ~/Baseball-private)
#   2. monthly update schedule
#   3. today's run: 2026 league pull, slim copies, edge engine
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
cd "$HOME/Baseball" || exit 1
git pull --ff-only
uv sync --quiet

echo "--- 1. Private repo ---"
if [ ! -d "$HOME/Baseball-private/.git" ]; then
  gh repo view IForSureI/Baseball-private >/dev/null 2>&1 || gh repo create IForSureI/Baseball-private --private \
    --description "Private: team data (UMass, Rogues), scouting notes, inbox. Never public."
  mkdir -p "$HOME/Baseball-private"
  cd "$HOME/Baseball-private"
  git init -q -b main
  mkdir -p inbox/trackman inbox/rapsodo inbox/notes inbox/other notes reports
  for d in inbox/trackman inbox/rapsodo inbox/notes inbox/other notes reports; do touch "$d/.gitkeep"; done
  cat > README.md <<'MD'
# Baseball-private

Private companion to the public `Baseball` repo. Team data and scouting notes live here and nowhere else.

| Folder | What goes in it |
|---|---|
| `inbox/trackman`, `inbox/rapsodo` | Raw exports, as downloaded. The loader converts them to the Statcast format. |
| `inbox/notes` | Scouting notes as they come in (dictated, typed, photos). |
| `inbox/other` | Anything else from coaches or the club. |
| `notes/` | Filed notes: dated, sourced, firsthand or secondhand. |
| `reports/` | Private reports built on team data. |

Rule: nothing from this repo is ever copied into the public `Baseball` repo.
MD
  git add -A && git commit -qm "Set up private workspace: inbox, notes, reports"
  git remote add origin https://github.com/IForSureI/Baseball-private.git
  git push -qu origin main && echo "Private repo ready: ~/Baseball-private"
  cd "$HOME/Baseball"
else
  echo "Private repo already set up."
fi

echo "--- 2. Monthly schedule ---"
zsh "$HOME/Baseball/scripts/automation/install.sh"

echo "--- 3. Today's run ---"
zsh "$HOME/Baseball/scripts/automation/update.sh"
echo
echo "All done. You can close this window."
