#!/bin/bash
# Tally Reports - One-Click Deployment Script
# Usage: ./deploy.sh

set -e

echo "========================================="
echo "  Tally Reports - Self-Hosted Deployment"
echo "========================================="
echo ""

# Check prerequisites
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed. Please install Docker first."
    echo "Visit: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "ERROR: Docker Compose is not installed."
    exit 1
fi

# Check for .env file
if [ ! -f .env ]; then
    echo "No .env file found. Creating from template..."
    cp .env.example .env
    echo ""
    echo "IMPORTANT: Edit .env file with your API keys before proceeding."
    echo "  - EMERGENT_LLM_KEY: Required for AI features"
    echo "  - RESEND_API_KEY: Optional (leave blank for dev mode)"
    echo ""
    read -p "Have you edited .env with your keys? (y/n): " confirm
    if [ "$confirm" != "y" ]; then
        echo "Please edit .env and run this script again."
        exit 1
    fi
fi

echo ""
echo "Building and starting services..."
echo ""

# Use docker compose (v2) if available, fallback to docker-compose
if docker compose version &> /dev/null 2>&1; then
    docker compose up -d --build
else
    docker-compose up -d --build
fi

echo ""
echo "========================================="
echo "  Deployment Complete!"
echo "========================================="
echo ""
echo "  Web App:     http://localhost"
echo "  Backend API: http://localhost:8001"
echo "  MongoDB:     localhost:27017"
echo ""
echo "  Login: Enter any email, use OTP 123456 (dev mode)"
echo ""
echo "  Desktop Sync Agent:"
echo "    cd desktop-agent && pip install -r requirements.txt"
echo "    python tally_sync_agent.py"
echo ""
echo "  To stop:  docker compose down"
echo "  To logs:  docker compose logs -f"
echo "========================================="
