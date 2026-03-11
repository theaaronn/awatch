#!/bin/bash
set -euo pipefail

REPO_ORG="YOUR_ORG"
REPO_NAME="awatch"

if [ "$EUID" -ne 0 ]; then
  echo "Error: This script must be run as root (use sudo)"
  exit 1
fi

ARCH=$(uname -m)
case "$ARCH" in
  x86_64)
    ARCH="amd64"
    ;;
  aarch64)
    ARCH="arm64"
    ;;
  *)
    echo "Error: Unsupported architecture: $ARCH"
    exit 1
    ;;
esac

if [ ! -f /etc/os-release ]; then
  echo "Error: Cannot detect OS. /etc/os-release not found."
  exit 1
fi

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

if systemctl is-active --quiet awatch-agent 2>/dev/null; then
  echo "Stopping existing awatch-agent service..."
  systemctl stop awatch-agent || true
fi

echo "Downloading awatch-agent..."
curl -fsSL -o /tmp/awatch-agent "https://github.com/${REPO_ORG}/${REPO_NAME}/releases/download/${VERSION}/awatch-agent-linux-${ARCH}"

echo "Installing binary..."
install -m 755 /tmp/awatch-agent /usr/local/bin/awatch-agent

echo "Creating config directory..."
mkdir -p /etc/awatch

echo "Writing config file..."
cat > /etc/awatch/agent.yaml << EOF
agent_id: "${AWATCH_AGENT_ID}"
broker_url: "${AWATCH_BROKER_URL}"
nats_url: "${AWATCH_NATS_URL}"
collection_interval: "1s"
batch_size: 10
log_level: "info"
tls_enabled: false
EOF

echo "Creating systemd service..."
cat > /etc/systemd/system/awatch-agent.service << 'EOF'
[Unit]
Description=Awatch Monitoring Agent
Documentation=https://github.com/YOUR_ORG/awatch
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/awatch-agent
Restart=on-failure
RestartSec=5s
User=nobody
Group=nogroup
EnvironmentFile=-/etc/awatch/agent.env
StandardOutput=journal
StandardError=journal
SyslogIdentifier=awatch-agent

# Hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/etc/awatch

[Install]
WantedBy=multi-user.target
EOF

echo "Reloading systemd daemon..."
systemctl daemon-reload

echo "Enabling and starting awatch-agent..."
systemctl enable awatch-agent
systemctl start awatch-agent

rm -f /tmp/awatch-agent

echo ""
echo "Awatch agent installed and started. Check status: systemctl status awatch-agent"
