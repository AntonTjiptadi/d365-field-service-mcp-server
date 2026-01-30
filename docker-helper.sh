#!/bin/bash
# ============================================
# Docker Build and Run Helper Script
# ============================================
# This script helps build and run the MCP D365 server container
# Usage: ./docker-helper.sh [build|run|test|push|clean]
# ============================================

set -e  # Exit on error

# Configuration
IMAGE_NAME="mcp-d365-server"
IMAGE_TAG="latest"
FULL_IMAGE_NAME="${IMAGE_NAME}:${IMAGE_TAG}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored messages
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if .env.trial exists
check_env_file() {
    if [ ! -f .env ]; then
        print_error ".env file not found!"
        print_info "Please create .env from .env.template"
        print_info "  cp .env.template .env"
        print_info "  # Then edit .env with your credentials"
        exit 1
    fi
}

# Function to build Docker image
build_image() {
    print_info "Building Docker image: ${FULL_IMAGE_NAME}"
    
    docker build \
        -t ${FULL_IMAGE_NAME} \
        -f Dockerfile \
        .
    
    if [ $? -eq 0 ]; then
        print_success "Docker image built successfully: ${FULL_IMAGE_NAME}"
        
        # Show image size
        SIZE=$(docker images ${FULL_IMAGE_NAME} --format "{{.Size}}")
        print_info "Image size: ${SIZE}"
    else
        print_error "Docker build failed!"
        exit 1
    fi
}

# Function to run container locally
run_container() {
    check_env_file
    
    print_info "Running container: ${FULL_IMAGE_NAME}"
    print_info "Loading environment from: .env"
    
    docker run -it --rm \
        --name mcp-d365-server-trial \
        --env-file .env \
        ${FULL_IMAGE_NAME}
}

# Function to run container in background
run_detached() {
    check_env_file
    
    print_info "Running container in background: ${FULL_IMAGE_NAME}"
    
    docker run -d \
        --name mcp-d365-server-trial \
        --env-file .env \
        --restart unless-stopped \
        ${FULL_IMAGE_NAME}
    
    if [ $? -eq 0 ]; then
        print_success "Container started in background"
        print_info "View logs: docker logs -f mcp-d365-server-trial"
        print_info "Stop container: docker stop mcp-d365-server-trial"
    fi
}

# Function to run container in HTTP mode (for Copilot Studio)
run_http() {
    check_env_file
    
    print_info "Running container in HTTP mode: ${FULL_IMAGE_NAME}"
    print_info "API will be available at: http://localhost:8000"
    print_info "MCP tools exposed as HTTP endpoints"
    
    docker run -it --rm \
        --name mcp-d365-server-http \
        --env-file .env \
        -e MCP_TRANSPORT=http \
        -p 8000:8000 \
        ${FULL_IMAGE_NAME}
}

# Function to run HTTP mode in background
run_http_detached() {
    check_env_file
    
    print_info "Running container in HTTP mode (background): ${FULL_IMAGE_NAME}"
    
    docker run -d \
        --name mcp-d365-server-http \
        --env-file .env \
        -e MCP_TRANSPORT=http \
        -p 8000:8000 \
        --restart unless-stopped \
        ${FULL_IMAGE_NAME}
    
    if [ $? -eq 0 ]; then
        print_success "HTTP API started in background"
        print_info "API available at: http://localhost:8000"
        print_info "View logs: docker logs -f mcp-d365-server-http"
        print_info "Stop container: docker stop mcp-d365-server-http"
    fi
}

# Function to test container
test_container() {
    check_env_file
    
     print_info "Testing container startup..."
    print_warning "Server will start and display banner. Press Ctrl+C when done."
    
    docker run -it --rm \
        --env-file .env \
        ${FULL_IMAGE_NAME}
}

# Function to push to container registry
push_image() {
    print_info "Pushing image to registry..."
    
    # Check if ACR_NAME is set
    if [ -z "$ACR_NAME" ]; then
        print_error "ACR_NAME environment variable not set!"
        print_info "Set it with: export ACR_NAME=your-registry.azurecr.io"
        exit 1
    fi
    
    # Tag for Azure Container Registry
    ACR_IMAGE="${ACR_NAME}/${IMAGE_NAME}:${IMAGE_TAG}"
    
    print_info "Tagging image: ${ACR_IMAGE}"
    docker tag ${FULL_IMAGE_NAME} ${ACR_IMAGE}
    
    print_info "Pushing to registry: ${ACR_IMAGE}"
    docker push ${ACR_IMAGE}
    
    if [ $? -eq 0 ]; then
        print_success "Image pushed successfully: ${ACR_IMAGE}"
    else
        print_error "Failed to push image!"
        exit 1
    fi
}

# Function to clean up Docker resources
clean() {
    print_info "Cleaning up Docker resources..."
    
    # Stop and remove container if running
    if docker ps -a | grep -q mcp-d365-server-trial; then
        print_info "Stopping and removing container..."
        docker stop mcp-d365-server-trial 2>/dev/null || true
        docker rm mcp-d365-server-trial 2>/dev/null || true
    fi
    
    # Remove image
    if docker images | grep -q ${IMAGE_NAME}; then
        print_info "Removing image: ${FULL_IMAGE_NAME}"
        docker rmi ${FULL_IMAGE_NAME} 2>/dev/null || true
    fi
    
    print_success "Cleanup complete"
}

# Function to show container logs
logs() {
    if docker ps | grep -q mcp-d365-server-trial; then
        print_info "Showing container logs (Ctrl+C to exit)..."
        docker logs -f mcp-d365-server-trial
    else
        print_error "Container is not running"
        exit 1
    fi
}

# Function to show help
show_help() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  build       Build Docker image"
    echo "  run         Run container interactively (foreground)"
    echo "  detach      Run container in background"
    echo "  http        Run container in HTTP mode (for Copilot Studio)"
    echo "  http-detach Run HTTP container in background"
    echo "  test        Test container with MCP Inspector"
    echo "  push        Push image to Azure Container Registry"
    echo "  logs        Show container logs"
    echo "  clean       Clean up Docker resources"
    echo "  help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 build              # Build the Docker image"
    echo "  $0 run                # Run container interactively"
    echo "  $0 detach             # Run in background"
    echo "  $0 logs               # View logs"
    echo "  $0 clean              # Clean up"
    echo ""
    echo "Environment Variables:"
    echo "  ACR_NAME              Azure Container Registry name (for push)"
    echo ""
}

# Main script logic
case "$1" in
    build)
        build_image
        ;;
    run)
        run_container
        ;;
    detach)
        run_detached
        ;;
    http)
        run_http
        ;;
    http-detach)
        run_http_detached
        ;;
    test)
        test_container
        ;;
    push)
        push_image
        ;;
    logs)
        logs
        ;;
    clean)
        clean
        ;;
    help|--help|-h|"")
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac
