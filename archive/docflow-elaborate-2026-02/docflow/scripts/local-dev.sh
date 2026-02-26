#!/usr/bin/env bash
# DocFlow Local Development Quick Start
# Sets up a full local development environment with K3D

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════════════╗"
echo "║           DocFlow Local Development Environment                   ║"
echo "╚═══════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# =============================================================================
# Prerequisites Check
# =============================================================================

check_command() {
    if ! command -v "$1" &> /dev/null; then
        echo -e "${RED}❌ $1 is not installed${NC}"
        return 1
    else
        echo -e "${GREEN}✓ $1 found${NC}"
        return 0
    fi
}

echo -e "${YELLOW}Checking prerequisites...${NC}"
echo ""

MISSING=0

check_command docker || MISSING=1
check_command kubectl || MISSING=1
check_command k3d || MISSING=1
check_command helm || MISSING=1

echo ""

if [ $MISSING -eq 1 ]; then
    echo -e "${RED}Missing required tools. Please install them:${NC}"
    echo ""
    echo "  brew install docker kubectl k3d helm"
    echo ""
    echo "Or see: https://k3d.io for installation instructions"
    exit 1
fi

# Check Docker is running
if ! docker info &> /dev/null; then
    echo -e "${RED}❌ Docker is not running. Please start Docker Desktop.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker is running${NC}"

# =============================================================================
# Parse Arguments
# =============================================================================

ACTION="${1:-start}"

case "$ACTION" in
    start|up)
        ACTION="start"
        ;;
    stop|down)
        ACTION="stop"
        ;;
    restart)
        ACTION="restart"
        ;;
    status)
        ACTION="status"
        ;;
    clean|destroy)
        ACTION="clean"
        ;;
    logs)
        COMPONENT="${2:-all}"
        ;;
    shell)
        COMPONENT="${2:-api}"
        ;;
    help|--help|-h)
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  start     Create cluster and deploy DocFlow (default)"
        echo "  stop      Stop the cluster (preserves data)"
        echo "  restart   Restart the cluster"
        echo "  status    Show cluster status"
        echo "  clean     Delete cluster and all data"
        echo "  logs      Show logs (api, agent, postgres, all)"
        echo "  shell     Open shell in container (api, agent)"
        echo "  help      Show this help"
        exit 0
        ;;
    *)
        echo -e "${RED}Unknown command: $ACTION${NC}"
        echo "Run '$0 help' for usage"
        exit 1
        ;;
esac

# =============================================================================
# Functions
# =============================================================================

cluster_exists() {
    k3d cluster list | grep -q "docflow-local"
}

start_cluster() {
    echo ""
    echo -e "${YELLOW}Starting DocFlow local environment...${NC}"
    echo ""
    
    cd "$PROJECT_ROOT/deploy/k3d"
    
    if cluster_exists; then
        echo -e "${BLUE}Cluster exists, starting it...${NC}"
        k3d cluster start docflow-local
    else
        echo -e "${BLUE}Creating new cluster...${NC}"
        make create-cluster
    fi
    
    echo ""
    echo -e "${BLUE}Deploying infrastructure...${NC}"
    make deploy-infra
    
    echo ""
    echo -e "${BLUE}Deploying Ollama (local LLM)...${NC}"
    make deploy-ollama
    
    echo ""
    echo -e "${BLUE}Building and deploying DocFlow...${NC}"
    make deploy-app
    
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                    Local Environment Ready!                        ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Access points:"
    echo "  📡 DocFlow API:    http://localhost:8080"
    echo "  🤖 Agent WebSocket: ws://localhost:8765"
    echo "  🗄️  PostgreSQL:     localhost:5432 (docflow/localdev)"
    echo ""
    echo "Quick commands:"
    echo "  $0 logs api      - View API logs"
    echo "  $0 logs agent    - View Agent logs"
    echo "  $0 shell api     - Shell into API container"
    echo "  $0 stop          - Stop cluster"
    echo "  $0 clean         - Delete everything"
    echo ""
}

stop_cluster() {
    echo -e "${YELLOW}Stopping cluster...${NC}"
    k3d cluster stop docflow-local
    echo -e "${GREEN}Cluster stopped. Run '$0 start' to resume.${NC}"
}

restart_cluster() {
    stop_cluster
    start_cluster
}

show_status() {
    echo -e "${YELLOW}Cluster Status${NC}"
    echo ""
    k3d cluster list
    echo ""
    
    if cluster_exists && kubectl cluster-info &> /dev/null; then
        echo -e "${YELLOW}Kubernetes Resources${NC}"
        echo ""
        kubectl get pods -n docflow
        echo ""
        kubectl get svc -n docflow
    else
        echo -e "${YELLOW}Cluster is not running${NC}"
    fi
}

clean_cluster() {
    echo -e "${RED}⚠️  This will delete the cluster and all data!${NC}"
    read -p "Are you sure? (y/N) " -n 1 -r
    echo ""
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Deleting cluster...${NC}"
        k3d cluster delete docflow-local || true
        rm -rf /tmp/k3d-docflow-storage
        echo -e "${GREEN}Cluster deleted.${NC}"
    else
        echo "Cancelled."
    fi
}

show_logs() {
    case "$COMPONENT" in
        api)
            kubectl logs -f -l app.kubernetes.io/name=docflow,app.kubernetes.io/component=api -n docflow
            ;;
        agent)
            kubectl logs -f -l app.kubernetes.io/name=docflow,app.kubernetes.io/component=agent -n docflow
            ;;
        postgres|postgresql|db)
            kubectl logs -f -l app.kubernetes.io/name=postgresql -n docflow
            ;;
        ollama|llm)
            kubectl logs -f -l app=ollama -n docflow
            ;;
        all|*)
            kubectl logs -f -l app.kubernetes.io/name=docflow -n docflow
            ;;
    esac
}

open_shell() {
    case "$COMPONENT" in
        api)
            kubectl exec -it -n docflow deploy/docflow-api -- /bin/bash
            ;;
        agent)
            kubectl exec -it -n docflow deploy/docflow-agent -- /bin/bash
            ;;
        db|postgres|postgresql)
            kubectl exec -it -n docflow postgresql-0 -- psql -U docflow -d docflow
            ;;
        *)
            echo "Unknown component: $COMPONENT"
            echo "Available: api, agent, db"
            exit 1
            ;;
    esac
}

# =============================================================================
# Main
# =============================================================================

case "$ACTION" in
    start)
        start_cluster
        ;;
    stop)
        stop_cluster
        ;;
    restart)
        restart_cluster
        ;;
    status)
        show_status
        ;;
    clean)
        clean_cluster
        ;;
    logs)
        show_logs
        ;;
    shell)
        open_shell
        ;;
esac
