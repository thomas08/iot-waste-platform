#!/bin/bash

# ===========================================
# GitHub Repository Setup Script
# ===========================================
#
# This script:
# 1. Installs GitHub CLI (gh) if not already installed
# 2. Authenticates with GitHub
# 3. Creates a new repository
# 4. Pushes code to GitHub
#
# Usage:
#   chmod +x setup_github.sh
#   ./setup_github.sh
#
# ===========================================

set -e

echo "=========================================="
echo "GitHub Repository Setup"
echo "=========================================="
echo ""

# Check if gh is already installed
if command -v gh &> /dev/null; then
    echo "✅ GitHub CLI is already installed"
    gh --version
else
    echo "📦 Installing GitHub CLI..."
    echo ""

    # Add GitHub CLI repository
    curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null
    sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null

    # Update and install
    sudo apt update
    sudo apt install gh -y

    echo "✅ GitHub CLI installed successfully"
fi

echo ""
echo "=========================================="
echo "GitHub Authentication"
echo "=========================================="
echo ""

# Check if already authenticated
if gh auth status &> /dev/null; then
    echo "✅ Already authenticated with GitHub"
    gh auth status
else
    echo "🔐 Please authenticate with GitHub..."
    echo ""
    echo "Choose one of these options:"
    echo "  1. Login with a web browser (recommended)"
    echo "  2. Paste an authentication token"
    echo ""
    gh auth login
fi

echo ""
echo "=========================================="
echo "Creating GitHub Repository"
echo "=========================================="
echo ""

# Repository details
REPO_NAME="iot-waste-platform"
REPO_DESC="IoT Waste Management Platform - Real-time monitoring system for smart waste collection using MQTT, PostgreSQL, and web dashboard"

echo "Repository name: $REPO_NAME"
echo "Description: $REPO_DESC"
echo ""

# Ask for visibility
read -p "Make repository public? (y/n) [default: y]: " IS_PUBLIC
IS_PUBLIC=${IS_PUBLIC:-y}

if [[ "$IS_PUBLIC" =~ ^[Yy]$ ]]; then
    VISIBILITY="--public"
else
    VISIBILITY="--private"
fi

echo ""
echo "Creating repository..."

# Create repository and push
gh repo create "$REPO_NAME" \
    $VISIBILITY \
    --source=. \
    --remote=origin \
    --description="$REPO_DESC" \
    --push

echo ""
echo "=========================================="
echo "✅ Success!"
echo "=========================================="
echo ""
echo "Your repository has been created and code has been pushed!"
echo ""
echo "Repository URL:"
gh repo view --web --json url -q .url 2>/dev/null || echo "https://github.com/thomas08/$REPO_NAME"
echo ""
echo "Next steps:"
echo "  - View repository: gh repo view --web"
echo "  - Clone elsewhere: git clone https://github.com/thomas08/$REPO_NAME.git"
echo "  - Add more commits: git add . && git commit -m 'message' && git push"
echo ""
echo "=========================================="
