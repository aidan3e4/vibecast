#!/bin/bash
# Installation script for Raspberry Pi / Orange Pi

set -e

echo "=================================="
echo "Snapshot Uploader Installation"
echo "=================================="
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "WARNING: Please run as normal user, not root"
    echo "Use: bash install-rpi.sh"
    exit 1
fi

# Update package list
echo "Updating package list..."
sudo apt-get update

# Install Python 3 and pip
echo "Installing Python 3 and pip..."
sudo apt-get install -y python3 python3-pip

# Install core dependencies
echo "Installing core dependencies..."
pip3 install --user -r requirements.txt

# Ask about S3
read -p "Will you use S3 storage backend? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Installing boto3 for S3 support..."
    pip3 install --user boto3
fi

# Create snapshots directory (default for filesystem backend)
mkdir -p ~/snapshots

# Copy example config
if [ ! -f .env ]; then
    echo "Creating .env file from example..."
    cp .env.example .env
    echo "Please edit .env file with your configuration"
else
    echo ".env file already exists, skipping..."
fi

# Make uploader executable
chmod +x uploader.py

echo ""
echo "=================================="
echo "Installation complete!"
echo "=================================="
echo ""
echo "Next steps:"
echo "1. Edit .env file with your camera and storage settings:"
echo "   nano .env"
echo ""
echo "2. Test the uploader:"
echo "   python3 uploader.py"
echo ""
echo "3. (Optional) Install as systemd service:"
echo "   bash install-service.sh"
echo ""
