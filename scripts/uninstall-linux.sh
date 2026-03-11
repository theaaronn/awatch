#!/bin/bash
set -euo pipefail

if [ "$EUID" -ne 0 ]; then
  echo "Error: This script must be run as root (use sudo)"
  exit 1
fi

echo "Stopping awatch-agent service..."
systemctl stop awatch-agent 2>/dev/null || true

echo "Disabling awatch-agent service..."
systemctl disable awatch-agent 2>/dev/null || true

echo "Removing systemd service file..."
rm -f /etc/systemd/system/awatch-agent.service

echo "Reloading systemd daemon..."
systemctl daemon-reload

echo "Removing binary..."
rm -f /usr/local/bin/awatch-agent

read -p "Remove configuration at /etc/awatch? [y/N]: " REMOVE_CONFIG
if [ "$REMOVE_CONFIG" = "y" ] || [ "$REMOVE_CONFIG" = "Y" ]; then
  rm -rf /etc/awatch
  echo "Configuration removed."
fi

echo ""
echo "Awatch agent uninstalled."
