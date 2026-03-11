#!/bin/bash
set -euo pipefail

echo "Unloading launchd agent..."
launchctl unload ~/Library/LaunchAgents/com.awatch.agent.plist 2>/dev/null || true

echo "Removing launchd plist..."
rm -f ~/Library/LaunchAgents/com.awatch.agent.plist

echo "Removing binary..."
sudo rm -f /usr/local/bin/awatch-agent

read -p "Remove configuration at ~/.config/awatch? [y/N]: " REMOVE_CONFIG
if [ "$REMOVE_CONFIG" = "y" ] || [ "$REMOVE_CONFIG" = "Y" ]; then
  rm -rf ~/.config/awatch
  echo "Configuration removed."
fi

echo ""
echo "Awatch agent uninstalled."
