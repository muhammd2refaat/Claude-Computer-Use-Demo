#!/bin/bash
# Docker Build Helper Script
# This script helps resolve common Docker build issues

echo "=========================================="
echo "  Computer-Use Agent - Docker Build Helper"
echo "=========================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running. Please start Docker first.${NC}"
    exit 1
fi

echo -e "${GREEN}Docker is running.${NC}"

# Fix 1: Pre-pull the base image
echo ""
echo -e "${YELLOW}Step 1: Pre-pulling Ubuntu base image...${NC}"
echo "This may take a few minutes depending on your network."

if docker pull ubuntu:22.04; then
    echo -e "${GREEN}Successfully pulled ubuntu:22.04${NC}"
else
    echo -e "${RED}Failed to pull ubuntu:22.04${NC}"
    echo ""
    echo "Trying alternative approaches:"

    # Try with explicit registry
    echo "Attempt 1: Explicit registry..."
    if docker pull docker.io/library/ubuntu:22.04; then
        echo -e "${GREEN}Success with docker.io registry${NC}"
    else
        echo -e "${YELLOW}Attempt 2: Restarting Docker daemon might help${NC}"
        echo "Please try: "
        echo "  1. Restart Docker Desktop"
        echo "  2. Or run: sudo systemctl restart docker"
        echo "  3. Then run this script again"
        exit 1
    fi
fi

# Fix 2: Clear Docker build cache if needed
echo ""
echo -e "${YELLOW}Step 2: Do you want to clear Docker build cache? (y/n)${NC}"
read -r response
if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    docker builder prune -f
    echo -e "${GREEN}Build cache cleared.${NC}"
fi

# Fix 3: Build the image
echo ""
echo -e "${YELLOW}Step 3: Building the Docker image...${NC}"

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Warning: .env file not found. Creating template...${NC}"
    cat > .env << 'EOF'
# Anthropic API Key (required)
ANTHROPIC_API_KEY=your_api_key_here

# Optional: Use a different model
# ANTHROPIC_MODEL=claude-haiku-4-5-20251001

# Optional: Custom base URL
# ANTHROPIC_BASE_URL=
EOF
    echo -e "${YELLOW}Please edit .env and add your ANTHROPIC_API_KEY${NC}"
fi

# Build with docker-compose
if docker-compose build --no-cache; then
    echo ""
    echo -e "${GREEN}=========================================="
    echo "  Build successful!"
    echo "==========================================${NC}"
    echo ""
    echo "To start the application:"
    echo "  docker-compose up"
    echo ""
    echo "To run tests:"
    echo "  python run_all_tests.py"
    echo ""
    echo "Access points:"
    echo "  Main UI:     http://localhost:8000"
    echo "  Test Page:   http://localhost:8000/test"
    echo "  API Docs:    http://localhost:8000/docs"
    echo "  Health:      http://localhost:8000/health"
else
    echo ""
    echo -e "${RED}Build failed. Common solutions:${NC}"
    echo ""
    echo "1. Network timeout - Try these DNS settings in Docker Desktop:"
    echo "   Settings > Docker Engine > Add:"
    echo '   "dns": ["8.8.8.8", "8.8.4.4"]'
    echo ""
    echo "2. Disk space - Free up space:"
    echo "   docker system prune -a"
    echo ""
    echo "3. Memory - Increase Docker memory allocation"
    echo "   (Docker Desktop > Settings > Resources > Memory)"
    echo ""
    echo "4. VPN/Proxy - Temporarily disable and retry"
    exit 1
fi
