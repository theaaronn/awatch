#!/bin/bash
set -euo pipefail

REPO_ORG="YOUR_ORG"
REPO_NAME="awatch"

ARCH=$(uname -m)
case "$ARCH" in
  x86_64)
    ARCH="amd64"
    ;;
  arm64)
    ARCH="arm64"
    ;;
  *)
    echo "Error: Unsupported architecture: $ARCH"
    exit 1
    ;;
esac

validate_agent_id() {
  local id="$1"
  if [[ ! "$id" =~ ^[a-zA-Z0-9_-]{1,64}$ ]]; then
    echo "Error: agent_id must be 1-64 characters: letters, numbers, underscore, hyphen"
    return 1
  fi
  return 0
}

validate_broker_url() {
  local url="$1"
  if [[ ! "$url" =~ ^[a-zA-Z0-9._-]+:[0-9]+$ ]]; then
    echo "Error: broker_url must be in format host:port"
    return 1
  fi
  return 0
}

validate_nats_url() {
  local url="$1"
  if [[ ! "$url" =~ ^nats:// ]]; then
    echo "Error: nats_url must start with nats://"
    return 1
  fi
  return 0
}

if [ -z "${AWATCH_AGENT_ID:-}" ]; then
  read -p "Enter a unique ID for this server (e.g. prod-web-01): " AWATCH_AGENT_ID
fi
validate_agent_id "$AWATCH_AGENT_ID"

if [ -z "${AWATCH_BROKER_URL:-}" ]; then
  read -p "Enter broker gRPC address (e.g. 10.0.0.1:50051): " AWATCH_BROKER_URL
fi
validate_broker_url "$AWATCH_BROKER_URL"

if [ -z "${AWATCH_NATS_URL:-}" ]; then
  read -p "Enter NATS URL (e.g. nats://10.0.0.1:4222): " AWATCH_NATS_URL
fi
validate_nats_url "$AWATCH_NATS_URL"

echo "Determining latest version..."
VERSION=$(curl -s "https://api.github.com/repos/${REPO_ORG}/${REPO_NAME}/releases/latest" | grep '"tag_name"' | cut -d'"' -f4)

if [ -z "$VERSION" ]; then
  echo "Error: Could not determine latest version"
  exit 1
fi

echo "Latest version: $VERSION"

launchctl unload ~/Library/LaunchAgents/com.awatch.agent.plist 2>/dev/null || true

echo "Downloading awatch-agent..."
curl -fsSL -o /tmp/awatch-agent "https://github.com/${REPO_ORG}/${REPO_NAME}/releases/download/${VERSION}/awatch-agent-darwin-${ARCH}"

echo "Installing binary..."
sudo install -m 755 /tmp/awatch-agent /usr/local/bin/awatch-agent

echo "Creating config directory..."
mkdir -p ~/.config/awatch

echo "Writing config file..."
cat > ~/.config/awatch/agent.yaml << EOF
agent_id: "${AWATCH_AGENT_ID}"
broker_url: "${AWATCH_BROKER_URL}"
nats_url: "${AWATCH_NATS_URL}"
collection_interval: "1s"
batch_size: 10
log_level: "info"
tls_enabled: false
EOF

echo "Creating launchd plist..."
cat > ~/Library/LaunchAgents/com.awatch.agent.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.awatch.agent</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/local/bin/awatch-agent</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>AWATCH_CONFIG</key>
    <string>$HOME/.config/awatch/agent.yaml</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>/tmp/awatch-agent.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/awatch-agent.err</string>
</dict>
</plist>
EOF

echo "Loading launchd agent..."
launchctl load ~/Library/LaunchAgents/com.awatch.agent.plist

rm -f /tmp/awatch-agent

echo ""
echo "Awatch agent installed. Check logs: tail -f /tmp/awatch-agent.log"
