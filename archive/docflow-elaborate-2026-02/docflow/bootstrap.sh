#!/usr/bin/env bash
# =============================================================================
# DocFlow Bootstrap - One-Step Local Development Setup
# =============================================================================
# 
# Usage: ./bootstrap.sh [options]
#
# This script will:
#   1. Check for required dependencies (docker, kubectl, k3d, helm, python)
#   2. Offer to install any missing dependencies automatically
#   3. Create and configure a local K3D cluster
#   4. Deploy PostgreSQL, Redis, Ollama, and DocFlow
#   5. Run initial health checks
#
# Options:
#   --yes, -y       Auto-accept all prompts (non-interactive)
#   --no-install    Skip automatic installation of missing dependencies
#   --verbose, -v   Enable verbose output
#   --dry-run       Show what would be done without doing it
#   --help, -h      Show this help message
#
# Requires: bash 3.2+, works on macOS and Linux
# =============================================================================

set -eo pipefail

# =============================================================================
# Configuration
# =============================================================================

VERSION="1.0.0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
LOG_FILE="${SCRIPT_DIR}/.bootstrap.log"

# Defaults
AUTO_YES="${AUTO_YES:-false}"
NO_INSTALL="${NO_INSTALL:-false}"
VERBOSE="${VERBOSE:-false}"
DRY_RUN="${DRY_RUN:-false}"

# Required dependencies (space-separated)
DEPS_REQUIRED="docker kubectl k3d helm"

# Optional dependencies
DEPS_OPTIONAL="python3 terraform aws"

# =============================================================================
# Logging & Output
# =============================================================================

# ANSI color codes - check if terminal supports colors
if [[ -t 1 ]] && [[ "${TERM:-dumb}" != "dumb" ]]; then
    C_RESET='\033[0m'
    C_RED='\033[0;31m'
    C_GREEN='\033[0;32m'
    C_YELLOW='\033[0;33m'
    C_BLUE='\033[0;34m'
    C_MAGENTA='\033[0;35m'
    C_CYAN='\033[0;36m'
    C_GRAY='\033[0;90m'
    C_BOLD='\033[1m'
    C_DIM='\033[2m'
else
    C_RESET=''
    C_RED=''
    C_GREEN=''
    C_YELLOW=''
    C_BLUE=''
    C_MAGENTA=''
    C_CYAN=''
    C_GRAY=''
    C_BOLD=''
    C_DIM=''
fi

# Emoji/Unicode symbols
SYM_CHECK="✓"
SYM_CROSS="✗"
SYM_WARN="⚠"
SYM_INFO="ℹ"
SYM_ARROW="→"
SYM_DOT="•"

# Track start time
START_TIME=$(date +%s)

# Initialize log file
init_log() {
    mkdir -p "$(dirname "$LOG_FILE")"
    cat > "$LOG_FILE" << EOF
========================================
DocFlow Bootstrap Log
Started: $(date)
Version: $VERSION
========================================

EOF
}

# Log to file only
log_file() {
    echo "[$(date '+%H:%M:%S')] $*" >> "$LOG_FILE"
}

# Print section header
section() {
    local title="$1"
    echo ""
    echo -e "${C_BOLD}${C_BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${C_RESET}"
    echo -e "${C_BOLD}${C_BLUE}  $title${C_RESET}"
    echo -e "${C_BOLD}${C_BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${C_RESET}"
    log_file "=== SECTION: $title ==="
}

# Print subsection
subsection() {
    local title="$1"
    echo ""
    echo -e "${C_CYAN}  ${SYM_ARROW} ${title}${C_RESET}"
    log_file "--- $title ---"
}

# Standard info message
info() {
    echo -e "${C_BLUE}${SYM_INFO}${C_RESET} $*"
    log_file "INFO: $*"
}

# Success message
success() {
    echo -e "${C_GREEN}${SYM_CHECK}${C_RESET} $*"
    log_file "SUCCESS: $*"
}

# Warning message
warn() {
    echo -e "${C_YELLOW}${SYM_WARN}${C_RESET} $*"
    log_file "WARN: $*"
}

# Error message
error() {
    echo -e "${C_RED}${SYM_CROSS}${C_RESET} $*" >&2
    log_file "ERROR: $*"
}

# Fatal error - exits script
fatal() {
    echo ""
    echo -e "${C_RED}${C_BOLD}Fatal Error:${C_RESET} $*" >&2
    log_file "FATAL: $*"
    echo ""
    echo -e "${C_GRAY}Check the log file for details: ${LOG_FILE}${C_RESET}"
    exit 1
}

# Debug message (only in verbose mode)
debug() {
    if [[ "$VERBOSE" == "true" ]]; then
        echo -e "${C_GRAY}  [debug] $*${C_RESET}"
    fi
    log_file "DEBUG: $*"
}

# Status line with result
print_status() {
    local description="$1"
    local stat="$2"
    local detail="${3:-}"
    
    if [[ "$stat" == "ok" ]]; then
        printf "  ${C_DIM}%-50s${C_RESET} ${C_GREEN}${SYM_CHECK} OK${C_RESET}" "$description"
        [[ -n "$detail" ]] && printf " ${C_GRAY}(%s)${C_RESET}" "$detail"
        echo ""
    elif [[ "$stat" == "missing" ]]; then
        printf "  ${C_DIM}%-50s${C_RESET} ${C_RED}${SYM_CROSS} Missing${C_RESET}\n" "$description"
    elif [[ "$stat" == "warn" ]]; then
        printf "  ${C_DIM}%-50s${C_RESET} ${C_YELLOW}${SYM_WARN} Warning${C_RESET}" "$description"
        [[ -n "$detail" ]] && printf " ${C_GRAY}(%s)${C_RESET}" "$detail"
        echo ""
    elif [[ "$stat" == "skip" ]]; then
        printf "  ${C_DIM}%-50s${C_RESET} ${C_GRAY}○ Skipped${C_RESET}" "$description"
        [[ -n "$detail" ]] && printf " ${C_GRAY}(%s)${C_RESET}" "$detail"
        echo ""
    else
        printf "  ${C_DIM}%-50s${C_RESET} %s\n" "$description" "$stat"
    fi
    
    log_file "STATUS: $description -> $stat $detail"
}

# Progress indicator for long operations
progress_start() {
    local msg="$1"
    echo -ne "  ${C_CYAN}◐${C_RESET} ${msg}..."
    log_file "PROGRESS START: $msg"
}

progress_done() {
    local result="${1:-done}"
    echo -e "\r  ${C_GREEN}${SYM_CHECK}${C_RESET} ${result}                    "
    log_file "PROGRESS DONE: $result"
}

progress_fail() {
    local msg="${1:-failed}"
    echo -e "\r  ${C_RED}${SYM_CROSS}${C_RESET} ${msg}                    "
    log_file "PROGRESS FAIL: $msg"
}

# Ask yes/no question
ask_yes_no() {
    local question="$1"
    local default="${2:-y}"
    
    if [[ "$AUTO_YES" == "true" ]]; then
        log_file "AUTO-YES: $question"
        return 0
    fi
    
    local prompt
    if [[ "$default" == "y" ]]; then
        prompt="[Y/n]"
    else
        prompt="[y/N]"
    fi
    
    echo -ne "${C_YELLOW}?${C_RESET} $question $prompt "
    read -r response
    response=${response:-$default}
    
    log_file "PROMPT: $question -> $response"
    
    [[ "$response" =~ ^[Yy] ]]
}

# Run command with optional dry-run
run_cmd() {
    local cmd="$*"
    
    log_file "CMD: $cmd"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        echo -e "  ${C_GRAY}[dry-run] Would execute: $cmd${C_RESET}"
        return 0
    fi
    
    if [[ "$VERBOSE" == "true" ]]; then
        echo -e "  ${C_GRAY}$ $cmd${C_RESET}"
        eval "$cmd" 2>&1 | tee -a "$LOG_FILE"
        return "${PIPESTATUS[0]}"
    else
        eval "$cmd" >> "$LOG_FILE" 2>&1
    fi
}

# =============================================================================
# System Detection
# =============================================================================

detect_os() {
    case "$(uname -s)" in
        Darwin)
            echo "macos"
            ;;
        Linux)
            echo "linux"
            ;;
        CYGWIN*|MINGW*|MSYS*)
            echo "windows"
            ;;
        *)
            echo "unknown"
            ;;
    esac
}

detect_arch() {
    local arch
    arch=$(uname -m)
    
    case "$arch" in
        x86_64|amd64)
            echo "amd64"
            ;;
        arm64|aarch64)
            echo "arm64"
            ;;
        *)
            echo "$arch"
            ;;
    esac
}

detect_package_manager() {
    local os="$1"
    
    case "$os" in
        macos)
            if command -v brew &>/dev/null; then
                echo "brew"
            else
                echo "none"
            fi
            ;;
        linux)
            if command -v apt-get &>/dev/null; then
                echo "apt"
            elif command -v dnf &>/dev/null; then
                echo "dnf"
            elif command -v yum &>/dev/null; then
                echo "yum"
            elif command -v pacman &>/dev/null; then
                echo "pacman"
            else
                echo "none"
            fi
            ;;
        *)
            echo "none"
            ;;
    esac
}

# =============================================================================
# Dependency Helpers
# =============================================================================

get_dep_description() {
    local dep="$1"
    case "$dep" in
        docker)   echo "Docker container runtime" ;;
        kubectl)  echo "Kubernetes CLI" ;;
        k3d)      echo "K3s in Docker" ;;
        helm)     echo "Kubernetes package manager" ;;
        python3)  echo "Python 3.x for development" ;;
        terraform) echo "Infrastructure as Code (for AWS deployment)" ;;
        aws)      echo "AWS CLI (for AWS deployment)" ;;
        *)        echo "$dep" ;;
    esac
}

check_dependency() {
    local dep="$1"
    
    if command -v "$dep" &>/dev/null; then
        local version
        version=$(get_version "$dep")
        echo "ok:$version"
    else
        echo "missing"
    fi
}

get_version() {
    local cmd="$1"
    local version=""
    
    case "$cmd" in
        docker)
            version=$(docker --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1) || true
            ;;
        kubectl)
            version=$(kubectl version --client -o json 2>/dev/null | grep -oE '"gitVersion":\s*"v[^"]+' | grep -oE 'v[0-9.]+' | head -1) || true
            ;;
        k3d)
            version=$(k3d version 2>/dev/null | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+' | head -1) || true
            ;;
        helm)
            version=$(helm version --short 2>/dev/null | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+') || true
            ;;
        python3)
            version=$(python3 --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+') || true
            ;;
        terraform)
            version=$(terraform --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+') || true
            ;;
        aws)
            version=$(aws --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1) || true
            ;;
        *)
            version=$($cmd --version 2>/dev/null | head -1) || true
            ;;
    esac
    
    echo "${version:-unknown}"
}

check_docker_running() {
    if docker info &>/dev/null; then
        echo "ok"
    else
        echo "not_running"
    fi
}

# =============================================================================
# Dependency Installation
# =============================================================================

install_homebrew() {
    info "Installing Homebrew (macOS package manager)..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        debug "Would install Homebrew"
        return 0
    fi
    
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # Add to PATH for this session
    if [[ -f /opt/homebrew/bin/brew ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [[ -f /usr/local/bin/brew ]]; then
        eval "$(/usr/local/bin/brew shellenv)"
    fi
}

install_dependency() {
    local dep="$1"
    local os="$2"
    local pkg_mgr="$3"
    
    debug "Installing $dep using $pkg_mgr on $os"
    
    case "$dep" in
        docker)
            case "$os" in
                macos)
                    if [[ "$pkg_mgr" == "brew" ]]; then
                        run_cmd "brew install --cask docker"
                        warn "Docker Desktop installed. Please launch it manually and wait for it to start."
                        echo ""
                        echo -e "  ${C_CYAN}${SYM_ARROW} Open Docker from Applications or run: open -a Docker${C_RESET}"
                        echo ""
                        
                        if ! ask_yes_no "Press Y when Docker is running to continue"; then
                            fatal "Docker must be running to continue"
                        fi
                    else
                        echo "  Please install Docker Desktop from: https://docker.com/products/docker-desktop"
                        return 1
                    fi
                    ;;
                linux)
                    if [[ "$pkg_mgr" == "apt" ]]; then
                        run_cmd "sudo apt-get update"
                        run_cmd "sudo apt-get install -y docker.io docker-compose"
                        run_cmd "sudo systemctl start docker"
                        run_cmd "sudo usermod -aG docker $USER"
                        warn "You may need to log out and back in for docker group changes to take effect"
                    else
                        echo "  Please install Docker: https://docs.docker.com/engine/install/"
                        return 1
                    fi
                    ;;
            esac
            ;;
        kubectl)
            case "$pkg_mgr" in
                brew)
                    run_cmd "brew install kubectl"
                    ;;
                apt)
                    run_cmd "sudo snap install kubectl --classic"
                    ;;
                *)
                    echo "  Please install kubectl: https://kubernetes.io/docs/tasks/tools/"
                    return 1
                    ;;
            esac
            ;;
        k3d)
            case "$pkg_mgr" in
                brew)
                    run_cmd "brew install k3d"
                    ;;
                *)
                    info "Installing k3d via install script..."
                    run_cmd "curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash"
                    ;;
            esac
            ;;
        helm)
            case "$pkg_mgr" in
                brew)
                    run_cmd "brew install helm"
                    ;;
                *)
                    info "Installing Helm via install script..."
                    run_cmd "curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash"
                    ;;
            esac
            ;;
        python3)
            case "$pkg_mgr" in
                brew)
                    run_cmd "brew install python@3.11"
                    ;;
                apt)
                    run_cmd "sudo apt-get install -y python3 python3-pip python3-venv"
                    ;;
                *)
                    echo "  Please install Python 3: https://python.org"
                    return 1
                    ;;
            esac
            ;;
        terraform)
            case "$pkg_mgr" in
                brew)
                    run_cmd "brew install terraform"
                    ;;
                *)
                    echo "  Please install Terraform: https://terraform.io/downloads"
                    return 1
                    ;;
            esac
            ;;
        aws)
            case "$pkg_mgr" in
                brew)
                    run_cmd "brew install awscli"
                    ;;
                *)
                    echo "  Please install AWS CLI: https://aws.amazon.com/cli/"
                    return 1
                    ;;
            esac
            ;;
        *)
            error "Unknown dependency: $dep"
            return 1
            ;;
    esac
    
    return 0
}

# =============================================================================
# Cluster Operations
# =============================================================================

cluster_exists() {
    k3d cluster list 2>/dev/null | grep -q "docflow-local"
}

wait_for_pods() {
    local namespace="$1"
    local timeout="${2:-300}"
    local check_interval=5
    local elapsed=0
    
    debug "Waiting for pods in namespace $namespace (timeout: ${timeout}s)"
    
    while [[ $elapsed -lt $timeout ]]; do
        local not_ready
        not_ready=$(kubectl get pods -n "$namespace" --no-headers 2>/dev/null | grep -v "Running\|Completed" | wc -l | tr -d ' ')
        
        if [[ "$not_ready" == "0" ]]; then
            return 0
        fi
        
        sleep $check_interval
        elapsed=$((elapsed + check_interval))
        debug "Waiting... ($elapsed/$timeout seconds, $not_ready pods not ready)"
    done
    
    warn "Timeout waiting for pods in $namespace"
    return 1
}

# =============================================================================
# Main Workflow
# =============================================================================

print_banner() {
    echo ""
    echo -e "${C_BOLD}${C_MAGENTA}"
    echo "  ╔═══════════════════════════════════════════════════════════════════╗"
    echo "  ║                                                                   ║"
    echo "  ║     ██████╗  ██████╗  ██████╗███████╗██╗      ██████╗ ██╗    ██╗  ║"
    echo "  ║     ██╔══██╗██╔═══██╗██╔════╝██╔════╝██║     ██╔═══██╗██║    ██║  ║"
    echo "  ║     ██║  ██║██║   ██║██║     █████╗  ██║     ██║   ██║██║ █╗ ██║  ║"
    echo "  ║     ██║  ██║██║   ██║██║     ██╔══╝  ██║     ██║   ██║██║███╗██║  ║"
    echo "  ║     ██████╔╝╚██████╔╝╚██████╗██║     ███████╗╚██████╔╝╚███╔███╔╝  ║"
    echo "  ║     ╚═════╝  ╚═════╝  ╚═════╝╚═╝     ╚══════╝ ╚═════╝  ╚══╝╚══╝   ║"
    echo "  ║                                                                   ║"
    echo "  ║           One-Step Local Development Bootstrap                    ║"
    echo "  ║                         v${VERSION}                                    ║"
    echo "  ║                                                                   ║"
    echo "  ╚═══════════════════════════════════════════════════════════════════╝"
    echo -e "${C_RESET}"
}

print_summary() {
    local end_time
    end_time=$(date +%s)
    local duration=$((end_time - START_TIME))
    local minutes=$((duration / 60))
    local seconds=$((duration % 60))
    
    echo ""
    echo -e "${C_BOLD}${C_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${C_RESET}"
    echo -e "${C_BOLD}${C_GREEN}  Setup Complete!                                                       ${C_RESET}"
    echo -e "${C_BOLD}${C_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${C_RESET}"
    echo ""
    echo -e "  ${C_DIM}Duration:${C_RESET} ${minutes}m ${seconds}s"
    echo -e "  ${C_DIM}Log file:${C_RESET} ${LOG_FILE}"
    echo ""
    echo -e "  ${C_BOLD}Quick Commands:${C_RESET}"
    echo ""
    echo -e "  ${C_CYAN}${SYM_DOT}${C_RESET} Check status:     ${C_GRAY}./scripts/local-dev.sh status${C_RESET}"
    echo -e "  ${C_CYAN}${SYM_DOT}${C_RESET} View API logs:    ${C_GRAY}./scripts/local-dev.sh logs api${C_RESET}"
    echo -e "  ${C_CYAN}${SYM_DOT}${C_RESET} View Agent logs:  ${C_GRAY}./scripts/local-dev.sh logs agent${C_RESET}"
    echo -e "  ${C_CYAN}${SYM_DOT}${C_RESET} Stop cluster:     ${C_GRAY}./scripts/local-dev.sh stop${C_RESET}"
    echo -e "  ${C_CYAN}${SYM_DOT}${C_RESET} Destroy cluster:  ${C_GRAY}./scripts/local-dev.sh clean${C_RESET}"
    echo ""
    echo -e "  ${C_BOLD}Access Points:${C_RESET}"
    echo ""
    echo -e "  ${C_CYAN}${SYM_DOT}${C_RESET} API:              ${C_BLUE}http://localhost:8080${C_RESET}"
    echo -e "  ${C_CYAN}${SYM_DOT}${C_RESET} Agent WebSocket:  ${C_BLUE}ws://localhost:8765${C_RESET}"
    echo -e "  ${C_CYAN}${SYM_DOT}${C_RESET} PostgreSQL:       ${C_GRAY}localhost:5432${C_RESET}"
    echo ""
}

print_help() {
    print_banner
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  --yes, -y       Auto-accept all prompts"
    echo "  --no-install    Don't offer to install missing dependencies"
    echo "  --verbose, -v   Show detailed output"
    echo "  --dry-run       Show what would be done without doing it"
    echo "  --help, -h      Show this help"
    echo ""
}

main() {
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --yes|-y)
                AUTO_YES=true
                shift
                ;;
            --no-install)
                NO_INSTALL=true
                shift
                ;;
            --verbose|-v)
                VERBOSE=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --help|-h)
                print_help
                exit 0
                ;;
            *)
                error "Unknown option: $1"
                echo "Run '$0 --help' for usage"
                exit 1
                ;;
        esac
    done
    
    # Initialize
    init_log
    print_banner
    
    if [[ "$DRY_RUN" == "true" ]]; then
        warn "Running in dry-run mode - no changes will be made"
    fi
    
    # =========================================================================
    # Phase 1: System Detection
    # =========================================================================
    
    section "System Detection"
    
    local os
    local arch
    local pkg_mgr
    
    os=$(detect_os)
    arch=$(detect_arch)
    pkg_mgr=$(detect_package_manager "$os")
    
    print_status "Operating System" "ok" "$os"
    print_status "Architecture" "ok" "$arch"
    
    if [[ "$pkg_mgr" == "none" ]]; then
        if [[ "$os" == "macos" ]]; then
            print_status "Package Manager" "missing"
            if [[ "$NO_INSTALL" != "true" ]] && ask_yes_no "Install Homebrew (recommended)?"; then
                install_homebrew
                pkg_mgr="brew"
                print_status "Homebrew" "ok" "just installed"
            else
                warn "No package manager available. You'll need to install dependencies manually."
            fi
        else
            print_status "Package Manager" "warn" "none detected"
        fi
    else
        print_status "Package Manager" "ok" "$pkg_mgr"
    fi
    
    # =========================================================================
    # Phase 2: Dependency Check
    # =========================================================================
    
    section "Dependency Check"
    
    subsection "Required Dependencies"
    
    local missing_required=""
    
    for dep in $DEPS_REQUIRED; do
        local result
        result=$(check_dependency "$dep")
        local check_status="${result%%:*}"
        local version="${result#*:}"
        local desc
        desc=$(get_dep_description "$dep")
        
        if [[ "$check_status" == "ok" ]]; then
            print_status "$desc" "ok" "$dep $version"
        else
            print_status "$desc" "missing"
            missing_required="$missing_required $dep"
        fi
    done
    
    subsection "Optional Dependencies"
    
    for dep in $DEPS_OPTIONAL; do
        local result
        result=$(check_dependency "$dep")
        local check_status="${result%%:*}"
        local version="${result#*:}"
        local desc
        desc=$(get_dep_description "$dep")
        
        if [[ "$check_status" == "ok" ]]; then
            print_status "$desc" "ok" "$dep $version"
        else
            print_status "$desc" "skip" "not required for local dev"
        fi
    done
    
    # Trim whitespace
    missing_required=$(echo "$missing_required" | xargs)
    
    # =========================================================================
    # Phase 3: Install Missing Dependencies
    # =========================================================================
    
    if [[ -n "$missing_required" ]]; then
        section "Installing Missing Dependencies"
        
        if [[ "$NO_INSTALL" == "true" ]]; then
            error "Missing required dependencies: $missing_required"
            fatal "Use without --no-install to auto-install, or install manually"
        fi
        
        if [[ "$pkg_mgr" == "none" ]]; then
            error "Cannot auto-install without a package manager"
            echo ""
            echo "Please install manually:"
            for dep in $missing_required; do
                local desc
                desc=$(get_dep_description "$dep")
                echo "  - $dep: $desc"
            done
            exit 1
        fi
        
        for dep in $missing_required; do
            local desc
            desc=$(get_dep_description "$dep")
            
            subsection "Installing $dep"
            
            if ! ask_yes_no "Install $dep ($desc)?"; then
                fatal "$dep is required but installation was declined"
            fi
            
            progress_start "Installing $dep"
            if install_dependency "$dep" "$os" "$pkg_mgr"; then
                progress_done "$dep installed successfully"
            else
                progress_fail "Failed to install $dep"
                fatal "Could not install $dep"
            fi
        done
    fi
    
    # =========================================================================
    # Phase 4: Docker Runtime Check
    # =========================================================================
    
    section "Docker Runtime Check"
    
    local docker_status
    docker_status=$(check_docker_running)
    
    if [[ "$docker_status" == "ok" ]]; then
        print_status "Docker daemon" "ok" "running"
    else
        print_status "Docker daemon" "missing" "not running"
        
        if [[ "$os" == "macos" ]]; then
            info "Starting Docker Desktop..."
            open -a Docker 2>/dev/null || true
            
            echo ""
            echo -e "  ${C_YELLOW}Waiting for Docker to start...${C_RESET}"
            echo -e "  ${C_GRAY}(This may take 30-60 seconds on first launch)${C_RESET}"
            echo ""
            
            local wait_count=0
            while [[ $(check_docker_running) != "ok" && $wait_count -lt 60 ]]; do
                sleep 2
                wait_count=$((wait_count + 1))
                echo -ne "\r  ${C_CYAN}◐${C_RESET} Waiting... (${wait_count}/60)"
            done
            echo ""
            
            if [[ $(check_docker_running) == "ok" ]]; then
                success "Docker is now running"
            else
                fatal "Docker failed to start. Please start Docker Desktop manually and re-run this script."
            fi
        else
            fatal "Docker is not running. Please start Docker and re-run this script."
        fi
    fi
    
    # =========================================================================
    # Phase 5: Create K3D Cluster
    # =========================================================================
    
    section "Kubernetes Cluster Setup"
    
    if cluster_exists; then
        print_status "K3D cluster 'docflow-local'" "ok" "exists"
        
        if ! k3d cluster list 2>/dev/null | grep "docflow-local" | grep -q "1/1"; then
            info "Starting existing cluster..."
            run_cmd "k3d cluster start docflow-local"
        fi
    else
        subsection "Creating K3D Cluster"
        
        progress_start "Creating cluster 'docflow-local'"
        
        if [[ -f "$PROJECT_ROOT/deploy/k3d/k3d-config.yaml" ]]; then
            run_cmd "k3d cluster create --config $PROJECT_ROOT/deploy/k3d/k3d-config.yaml"
        else
            run_cmd "k3d cluster create docflow-local \
                --api-port 6550 \
                --port '8080:80@loadbalancer' \
                --port '8443:443@loadbalancer' \
                --agents 1 \
                --registry-create docflow-registry:0.0.0.0:5111"
        fi
        
        progress_done "Cluster created"
    fi
    
    # Set kubectl context
    run_cmd "kubectl config use-context k3d-docflow-local"
    print_status "kubectl context" "ok" "k3d-docflow-local"
    
    # =========================================================================
    # Phase 6: Deploy Infrastructure
    # =========================================================================
    
    section "Infrastructure Deployment"
    
    subsection "Creating Namespace"
    run_cmd "kubectl create namespace docflow --dry-run=client -o yaml | kubectl apply -f -"
    print_status "Namespace 'docflow'" "ok" "ready"
    
    subsection "Deploying PostgreSQL"
    progress_start "Installing PostgreSQL with pgvector"
    
    run_cmd "helm repo add bitnami https://charts.bitnami.com/bitnami 2>/dev/null || true"
    run_cmd "helm repo update"
    
    if [[ -f "$PROJECT_ROOT/deploy/k3d/values/postgresql-local.yaml" ]]; then
        run_cmd "helm upgrade --install postgresql bitnami/postgresql \
            --namespace docflow \
            --values $PROJECT_ROOT/deploy/k3d/values/postgresql-local.yaml \
            --wait --timeout 5m"
    else
        run_cmd "helm upgrade --install postgresql bitnami/postgresql \
            --namespace docflow \
            --set auth.username=docflow \
            --set auth.password=localdev \
            --set auth.database=docflow \
            --wait --timeout 5m"
    fi
    
    progress_done "PostgreSQL deployed"
    
    subsection "Deploying Redis"
    progress_start "Installing Redis"
    
    if [[ -f "$PROJECT_ROOT/deploy/k3d/values/redis-local.yaml" ]]; then
        run_cmd "helm upgrade --install redis bitnami/redis \
            --namespace docflow \
            --values $PROJECT_ROOT/deploy/k3d/values/redis-local.yaml \
            --wait --timeout 3m"
    else
        run_cmd "helm upgrade --install redis bitnami/redis \
            --namespace docflow \
            --set architecture=standalone \
            --set auth.enabled=false \
            --wait --timeout 3m"
    fi
    
    progress_done "Redis deployed"
    
    # =========================================================================
    # Phase 7: Deploy Ollama (Local LLM)
    # =========================================================================
    
    section "Local LLM Setup (Ollama)"
    
    if [[ -f "$PROJECT_ROOT/deploy/k3d/manifests/ollama.yaml" ]]; then
        progress_start "Deploying Ollama"
        run_cmd "kubectl apply -f $PROJECT_ROOT/deploy/k3d/manifests/ollama.yaml -n docflow"
        progress_done "Ollama deployed"
        
        info "Ollama will pull models in the background (this may take a few minutes)"
    else
        print_status "Ollama manifest" "skip" "not found"
    fi
    
    # =========================================================================
    # Phase 8: Health Check
    # =========================================================================
    
    section "Health Verification"
    
    progress_start "Waiting for pods to be ready"
    if wait_for_pods "docflow" 180; then
        progress_done "All pods ready"
    else
        progress_fail "Some pods not ready (check logs)"
    fi
    
    echo ""
    info "Current pod status:"
    kubectl get pods -n docflow --no-headers 2>/dev/null | while read -r line; do
        local name status_col
        name=$(echo "$line" | awk '{print $1}')
        status_col=$(echo "$line" | awk '{print $3}')
        if [[ "$status_col" == "Running" ]]; then
            echo -e "  ${C_GREEN}${SYM_CHECK}${C_RESET} $name"
        elif [[ "$status_col" == "Completed" ]]; then
            echo -e "  ${C_GRAY}○${C_RESET} $name (completed)"
        else
            echo -e "  ${C_YELLOW}${SYM_WARN}${C_RESET} $name ($status_col)"
        fi
    done
    
    # =========================================================================
    # Done!
    # =========================================================================
    
    print_summary
}

# Run main
main "$@"
