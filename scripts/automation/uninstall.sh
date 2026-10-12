#!/bin/zsh
LABEL="com.dylanfanelli.baseball.update"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null
rm -f "$HOME/Library/LaunchAgents/$LABEL.plist" && echo "Monthly update removed."
