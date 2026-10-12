#!/bin/zsh -l
# Install the monthly update (1st of the month, 6:00 AM) as a macOS LaunchAgent.
# Remove it any time with: ~/Baseball/scripts/automation/uninstall.sh
LABEL="com.dylanfanelli.baseball.update"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Baseball/data/logs"
cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>/bin/zsh</string><string>-l</string><string>$HOME/Baseball/scripts/automation/update.sh</string></array>
  <key>StartCalendarInterval</key>
  <dict><key>Day</key><integer>1</integer><key>Hour</key><integer>6</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardOutPath</key><string>$HOME/Baseball/data/logs/launchagent.log</string>
  <key>StandardErrorPath</key><string>$HOME/Baseball/data/logs/launchagent.log</string>
</dict>
</plist>
PLIST
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null
launchctl bootstrap "gui/$(id -u)" "$PLIST" && echo "Monthly update installed: 1st of each month, 6:00 AM."
