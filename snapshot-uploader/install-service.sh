#!/bin/bash
# Install snapshot uploader as a systemd service

set -e

echo "=================================="
echo "Installing Systemd Service"
echo "=================================="
echo ""

# Check if running as normal user
if [ "$EUID" -eq 0 ]; then
    echo "ERROR: Please run as normal user, not root"
    echo "The script will use sudo when needed"
    exit 1
fi

# Get current directory and user
CURRENT_DIR=$(pwd)
CURRENT_USER=$(whoami)

echo "Installing service for user: $CURRENT_USER"
echo "Working directory: $CURRENT_DIR"
echo ""

# Create systemd service file
SERVICE_FILE="/etc/systemd/system/snapshot-uploader.service"

echo "Creating service file: $SERVICE_FILE"
sudo tee $SERVICE_FILE > /dev/null <<EOF
[Unit]
Description=Camera Snapshot Uploader Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$CURRENT_DIR
Environment="PATH=/usr/local/bin:/usr/bin:/bin"

# Load environment from .env file
EnvironmentFile=$CURRENT_DIR/.env

ExecStart=/usr/bin/python3 $CURRENT_DIR/uploader.py
Restart=always
RestartSec=10

# Logging
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
echo "Reloading systemd daemon..."
sudo systemctl daemon-reload

# Enable service
echo "Enabling service to start on boot..."
sudo systemctl enable snapshot-uploader

echo ""
echo "=================================="
echo "Service installed successfully!"
echo "=================================="
echo ""
echo "To start the service:"
echo "  sudo systemctl start snapshot-uploader"
echo ""
echo "To check status:"
echo "  sudo systemctl status snapshot-uploader"
echo ""
echo "To view logs:"
echo "  sudo journalctl -u snapshot-uploader -f"
echo ""
echo "To stop the service:"
echo "  sudo systemctl stop snapshot-uploader"
echo ""
echo "To disable auto-start on boot:"
echo "  sudo systemctl disable snapshot-uploader"
echo ""
