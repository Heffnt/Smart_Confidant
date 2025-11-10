#! /bin/bash

# ============================================================================
# Smart Confidant - Docker Deployment Script for Melnibone
# Deploys from laptop to melnibone.wpi.edu using Docker
# ============================================================================

set -e  # Exit on error

# Configuration
PORT=2222
MACHINE=melnibone.wpi.edu
USER=group12
MY_KEY_PATH=$HOME/.ssh/mlops  # Path to your SSH key for melnibone

# Docker configuration
DOCKER_USER=heffnt
DOCKER_IMAGE=smart_confidant
DOCKER_TAG=cs3
FULL_IMAGE_NAME=${DOCKER_USER}/${DOCKER_IMAGE}:${DOCKER_TAG}

# Container configuration
CONTAINER_NAME=smart_confidant
GRADIO_PORT=2727
METRICS_PORT=2728
NODE_EXPORTER_PORT=2729

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}→${NC} $1"
}

log_success() {
    echo -e "${GREEN}✓${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1"
}

# Load environment variables from .env file if it exists
if [ -f .env ]; then
    log_info "Loading environment variables from .env file..."
    export $(grep -v '^#' .env | xargs)
fi

# Check if HF_TOKEN is set
if [ -z "$HF_TOKEN" ]; then
    log_warning "HF_TOKEN not set - API models will not work"
    log_warning "Set it in .env file or export HF_TOKEN=your_token"
else
    log_success "HF_TOKEN found"
fi

# ============================================================================
# Step 1: Build Docker Image Locally
# ============================================================================
echo ""
echo "========================================"
echo "Step 1: Building Docker Image"
echo "========================================"

log_info "Building Docker image: ${FULL_IMAGE_NAME}"
if docker build -t ${FULL_IMAGE_NAME} .; then
    log_success "Docker image built successfully"
else
    log_error "Docker build failed"
    exit 1
fi

# ============================================================================
# Step 2: Push to DockerHub
# ============================================================================
echo ""
echo "========================================"
echo "Step 2: Pushing to DockerHub"
echo "========================================"

log_info "Checking Docker login status..."
if docker info 2>/dev/null | grep -q "Username: ${DOCKER_USER}"; then
    log_success "Already logged in to DockerHub as ${DOCKER_USER}"
elif docker login --username ${DOCKER_USER} 2>/dev/null; then
    log_success "Logged in to DockerHub"
else
    log_error "Not logged in to DockerHub"
    log_info "Please run: docker login --username ${DOCKER_USER}"
    exit 1
fi

log_info "Pushing image to DockerHub..."
if docker push ${FULL_IMAGE_NAME}; then
    log_success "Image pushed to DockerHub"
else
    log_error "Failed to push image to DockerHub"
    exit 1
fi

# ============================================================================
# Step 3: Verify SSH Access to Melnibone
# ============================================================================
echo ""
echo "========================================"
echo "Step 3: Verifying SSH Access"
echo "========================================"

# Clean up known_hosts entry for melnibone
ssh-keygen -f "$HOME/.ssh/known_hosts" -R "[${MACHINE}]:${PORT}" 2>/dev/null || true

if [ ! -f "${MY_KEY_PATH}" ]; then
    log_error "SSH key not found at ${MY_KEY_PATH}"
    log_info "Please ensure your SSH key is set up correctly"
    exit 1
fi

log_info "Testing SSH connection to ${USER}@${MACHINE}:${PORT}..."
if ssh -i ${MY_KEY_PATH} -p ${PORT} -o StrictHostKeyChecking=no -o ConnectTimeout=10 ${USER}@${MACHINE} "echo 'success'" > /dev/null 2>&1; then
    log_success "SSH connection successful"
else
    log_error "SSH connection failed"
    log_info "Make sure you can connect with: ssh -i ${MY_KEY_PATH} -p ${PORT} ${USER}@${MACHINE}"
    exit 1
fi

# ============================================================================
# Step 4: Deploy to Melnibone
# ============================================================================
echo ""
echo "========================================"
echo "Step 4: Deploying to Melnibone"
echo "========================================"

# Define SSH command
SSH_CMD="ssh -i ${MY_KEY_PATH} -p ${PORT} -o StrictHostKeyChecking=no ${USER}@${MACHINE}"

log_info "Deploying to remote server..."

# Run deployment commands on remote server
${SSH_CMD} bash -s << ENDSSH
set -e

echo "→ Pulling Docker image from DockerHub..."
if docker pull ${FULL_IMAGE_NAME}; then
    echo "✓ Image pulled successfully"
else
    echo "✗ Failed to pull image"
    exit 1
fi

echo "→ Stopping existing container if running..."
docker stop ${CONTAINER_NAME} 2>/dev/null || echo "  (no container to stop)"

echo "→ Removing existing container..."
docker rm ${CONTAINER_NAME} 2>/dev/null || echo "  (no container to remove)"

echo "→ Starting new container..."
docker run -d \\
    --name ${CONTAINER_NAME} \\
    -p ${GRADIO_PORT}:8012 \\
    -p ${METRICS_PORT}:8000 \\
    -p ${NODE_EXPORTER_PORT}:9100 \\
    -e HF_TOKEN="${HF_TOKEN}" \\
    ${FULL_IMAGE_NAME}

if [ \$? -eq 0 ]; then
    echo "✓ Container started successfully"
else
    echo "✗ Failed to start container"
    exit 1
fi

# Wait for container to be ready
echo "→ Waiting for container to start..."
sleep 5

# Verify container is running
if docker ps | grep -q ${CONTAINER_NAME}; then
    echo "✓ Container is running"
else
    echo "✗ Container failed to start"
    docker logs ${CONTAINER_NAME}
    exit 1
fi

# Verify ports are accessible
echo "→ Verifying ports..."
curl -s -o /dev/null -w "%{http_code}" http://localhost:${GRADIO_PORT} | grep -q "200" && echo "✓ Gradio port ${GRADIO_PORT} is accessible"
curl -s http://localhost:${METRICS_PORT}/metrics | grep -q "smart_confidant" && echo "✓ Metrics port ${METRICS_PORT} is accessible"
curl -s http://localhost:${NODE_EXPORTER_PORT}/metrics | grep -q "node_" && echo "✓ Node exporter port ${NODE_EXPORTER_PORT} is accessible"

ENDSSH

if [ $? -eq 0 ]; then
    log_success "Deployment to melnibone completed successfully"
else
    log_error "Deployment failed"
    exit 1
fi

# ============================================================================
# Step 5: Setup ngrok Tunnel
# ============================================================================
echo ""
echo "========================================"
echo "Step 5: Setting up ngrok Tunnel"
echo "========================================"

log_info "Setting up ngrok tunnel for global access..."

${SSH_CMD} bash -s << 'ENDSSH'
set -e

# Kill any existing ngrok processes for this port
echo "→ Stopping existing ngrok tunnels for port 2727..."
pkill -f "ngrok http 2727" 2>/dev/null || echo "  (no existing tunnel to stop)"
sleep 2

# Start new ngrok tunnel
echo "→ Starting ngrok tunnel..."
nohup ngrok http 2727 --log=stdout > ~/ngrok_smart_confidant.log 2>&1 &
NGROK_PID=$!

# Wait for ngrok to start
sleep 5

# Check if ngrok started successfully
if ps -p $NGROK_PID > /dev/null 2>&1; then
    echo "✓ ngrok started successfully (PID: $NGROK_PID)"

    # Extract the ngrok URL from the log
    NGROK_URL=$(grep -o "url=https://[^ ]*" ~/ngrok_smart_confidant.log | head -1 | cut -d'=' -f2)

    if [ ! -z "$NGROK_URL" ]; then
        echo "NGROK_URL=$NGROK_URL"
    else
        echo "⚠ Could not extract ngrok URL from log"
        echo "Check ~/ngrok_smart_confidant.log on the server"
    fi
else
    echo "✗ ngrok failed to start"
    cat ~/ngrok_smart_confidant.log
    exit 1
fi
ENDSSH

# Extract the ngrok URL from the SSH output
NGROK_URL=$(${SSH_CMD} "grep -o 'url=https://[^ ]*' ~/ngrok_smart_confidant.log | head -1 | cut -d'=' -f2")

# ============================================================================
# Deployment Summary
# ============================================================================
echo ""
echo "=========================================="
echo "🎉 DEPLOYMENT COMPLETE!"
echo "=========================================="
echo ""
echo "Docker Image: ${FULL_IMAGE_NAME}"
echo "Container Name: ${CONTAINER_NAME}"
echo ""
echo "Access URLs:"
echo "  🌐 Public URL (ngrok):  ${NGROK_URL}"
echo "  🏠 Local Gradio:        http://localhost:${GRADIO_PORT}"
echo "  📊 App Metrics:         http://localhost:${METRICS_PORT}/metrics"
echo "  🖥️  System Metrics:      http://localhost:${NODE_EXPORTER_PORT}/metrics"
echo ""
echo "Port Mappings:"
echo "  ${GRADIO_PORT} → 8012 (Gradio Interface)"
echo "  ${METRICS_PORT} → 8000 (Application Metrics)"
echo "  ${NODE_EXPORTER_PORT} → 9100 (Node Exporter)"
echo ""
echo "Container Management:"
echo "  View logs:    ssh -i ${MY_KEY_PATH} -p ${PORT} ${USER}@${MACHINE} 'docker logs ${CONTAINER_NAME}'"
echo "  Stop:         ssh -i ${MY_KEY_PATH} -p ${PORT} ${USER}@${MACHINE} 'docker stop ${CONTAINER_NAME}'"
echo "  Restart:      ssh -i ${MY_KEY_PATH} -p ${PORT} ${USER}@${MACHINE} 'docker restart ${CONTAINER_NAME}'"
echo ""
echo "=========================================="
