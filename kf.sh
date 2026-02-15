#!/usr/bin/env bash
# Knowledge Foundry DevOps Management Script
# Manages the entire application stack: infrastructure + application + monitoring

set -euo pipefail

# ============================================================================
# CONFIGURATION
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="knowledge-foundry"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.yml"
VENV_DIR="${SCRIPT_DIR}/.venv"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

log_info() {
    echo -e "${BLUE}ℹ${NC} $*"
}

log_success() {
    echo -e "${GREEN}✓${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}⚠${NC} $*"
}

log_error() {
    echo -e "${RED}✗${NC} $*"
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker Desktop."
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running. Please start Docker Desktop."
        exit 1
    fi
}

check_compose_file() {
    if [[ ! -f "$COMPOSE_FILE" ]]; then
        log_error "docker-compose.yml not found at: $COMPOSE_FILE"
        exit 1
    fi
}

wait_for_health() {
    local service=$1
    local port=$2
    local path=${3:-}
    local max_attempts=${4:-30}
    local attempt=0
    
    log_info "Waiting for $service to be ready (Port $port)..."
    
    while [[ $attempt -lt $max_attempts ]]; do
        # Check if container is running first
        if ! docker compose -f "$COMPOSE_FILE" ps "$service" | grep -q "Up"; then
            log_warn "$service container is not running yet..."
        else
            # Try to connect to the port
            if [[ -n "$path" ]]; then
                # HTTP check
                if curl -s -f "http://localhost:${port}${path}" >/dev/null; then
                    log_success "$service is healthy"
                    return 0
                fi
            else
                # TCP check (using nc or bash tcp)
                if nc -z localhost "$port" 2>/dev/null; then
                    log_success "$service is ready"
                    return 0
                fi
            fi
        fi
        
        attempt=$((attempt + 1))
        rm -f /tmp/kf_health_check_$service
        sleep 2
        echo -n "."
    done
    
    echo ""
    log_warn "$service health check timed out after $((max_attempts * 2))s"
    return 1
}

# ============================================================================
# MAIN COMMANDS
# ============================================================================

cmd_start() {
    log_info "Starting Knowledge Foundry stack..."
    
    check_docker
    check_compose_file
    
    # Start infrastructure services first
    log_info "Step 1/4: Starting infrastructure (Qdrant, Redis, PostgreSQL, Neo4j)..."
    docker compose -f "$COMPOSE_FILE" up -d qdrant redis postgres neo4j
    
    # Wait for infrastructure health
    # Qdrant (6333) - HTTP healthz
    wait_for_health "qdrant" 6333 "/healthz" 30
    # Redis (6379) - TCP
    wait_for_health "redis" 6379 "" 30
    # Postgres (5432) - TCP
    wait_for_health "postgres" 5432 "" 30
    # Neo4j (7474) - HTTP
    wait_for_health "neo4j" 7474 "" 40
    
    # Start application
    log_info "Step 2/4: Starting application (API)..."
    docker compose -f "$COMPOSE_FILE" up -d api
    # API (8000) - HTTP /health
    wait_for_health "api" 8000 "/health" 60
    
    # Start frontend
    log_info "Step 3/4: Starting frontend..."
    docker compose -f "$COMPOSE_FILE" up -d frontend
    # Frontend (3000) - HTTP
    wait_for_health "frontend" 3000 "" 40
    
    # Start monitoring
    log_info "Step 4/4: Starting monitoring (Prometheus, Grafana)..."
    docker compose -f "$COMPOSE_FILE" up -d prometheus grafana
    
    echo ""
    log_success "Knowledge Foundry is running!"
    echo ""
    echo "📊 Service URLs:"
    echo "   Frontend:    http://localhost:3000"
    echo "   API:         http://localhost:8000"
    echo "   API Docs:    http://localhost:8000/docs"
    echo "   Grafana:     http://localhost:3001 (admin/kf_admin)"
    echo "   Prometheus:  http://localhost:9090"
    echo "   Neo4j:       http://localhost:7474 (neo4j/kf_dev_password)"
    echo ""
}

cmd_stop() {
    log_info "Stopping Knowledge Foundry stack..."
    
    check_docker
    check_compose_file
    
    docker compose -f "$COMPOSE_FILE" down
    
    log_success "All services stopped"
}

cmd_restart() {
    log_info "Restarting Knowledge Foundry stack..."
    cmd_stop
    sleep 2
    cmd_start
}

cmd_status() {
    check_docker
    check_compose_file
    
    echo ""
    echo "📊 Knowledge Foundry Stack Status"
    echo "=================================="
    echo ""
    
    docker compose -f "$COMPOSE_FILE" ps
    
    echo ""
    echo "🔍 Health Status:"
    
    services=("qdrant" "redis" "postgres" "neo4j" "api" "frontend" "prometheus" "grafana")
    
    for service in "${services[@]}"; do
        if docker compose -f "$COMPOSE_FILE" ps "$service" 2>/dev/null | grep -q "Up"; then
            echo -e "   ${GREEN}●${NC} $service (running)"
        else
            echo -e "   ${RED}●${NC} $service (stopped)"
        fi
    done
    
    echo ""
}

cmd_logs() {
    local service=${1:-}
    
    check_docker
    check_compose_file
    
    if [[ -z "$service" ]]; then
        log_info "Showing logs for all services (Ctrl+C to exit)..."
        docker compose -f "$COMPOSE_FILE" logs -f
    else
        log_info "Showing logs for: $service (Ctrl+C to exit)..."
        docker compose -f "$COMPOSE_FILE" logs -f "$service"
    fi
}

cmd_clean() {
    log_warn "This will remove all containers, volumes, and data. Are you sure? [y/N]"
    read -r response
    
    if [[ "$response" =~ ^[Yy]$ ]]; then
        log_info "Stopping and removing all services and volumes..."
        
        check_docker
        check_compose_file
        
        docker compose -f "$COMPOSE_FILE" down -v
        
        log_success "All services, volumes, and data removed"
    else
        log_info "Clean cancelled"
    fi
}

cmd_rebuild() {
    log_info "Rebuilding application images..."
    
    check_docker
    check_compose_file
    
    docker compose -f "$COMPOSE_FILE" build --no-cache api frontend
    
    log_success "Images rebuilt"
    log_info "Run './kf.sh restart' to apply changes"
}

cmd_test() {
    log_info "Running test suite..."
    
    if [[ ! -d "$VENV_DIR" ]]; then
        log_error "Virtual environment not found. Please run: python -m venv .venv && .venv/bin/pip install -e '.[dev]'"
        exit 1
    fi
    
    "$VENV_DIR/bin/python" -m pytest tests/ --tb=short -q
}

cmd_shell() {
    local service=${1:-api}
    
    check_docker
    check_compose_file
    
    log_info "Opening shell in: $service"
    docker compose -f "$COMPOSE_FILE" exec "$service" /bin/sh
}

cmd_db_migrate() {
    log_info "Running database migrations..."
    
    check_docker
    check_compose_file
    
    # Ensure postgres is running
    if ! docker compose -f "$COMPOSE_FILE" ps postgres 2>/dev/null | grep -q "Up"; then
        log_error "PostgreSQL is not running. Start it with: ./kf.sh start"
        exit 1
    fi
    
    docker compose -f "$COMPOSE_FILE" exec api python -m alembic upgrade head
    
    log_success "Migrations complete"
}

cmd_help() {
    cat << EOF

Knowledge Foundry - DevOps Management Script
============================================

Usage: ./kf.sh <command> [options]

Commands:
  start       Start the entire stack (infrastructure → app → monitoring)
  stop        Stop all services
  restart     Restart all services
  status      Show status of all services
  logs [svc]  Show logs (all services or specific service)
  clean       Remove all containers and volumes (⚠ destroys data)
  rebuild     Rebuild application Docker images
  test        Run test suite (requires local venv)
  shell [svc] Open shell in service container (default: api)
  db-migrate  Run database migrations
  help        Show this help message

Examples:
  ./kf.sh start              # Start everything
  ./kf.sh status             # Check what's running
  ./kf.sh logs api           # View API logs
  ./kf.sh shell postgres     # Connect to PostgreSQL container
  ./kf.sh restart            # Restart all services

Service URLs (after start):
  Frontend:    http://localhost:3000
  API:         http://localhost:8000
  API Docs:    http://localhost:8000/docs
  Grafana:     http://localhost:3001 (admin/kf_admin)
  Prometheus:  http://localhost:9090
  Neo4j:       http://localhost:7474 (neo4j/kf_dev_password)

EOF
}

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

main() {
    local command=${1:-help}
    
    case $command in
        start)
            cmd_start
            ;;
        stop)
            cmd_stop
            ;;
        restart)
            cmd_restart
            ;;
        status)
            cmd_status
            ;;
        logs)
            cmd_logs "${2:-}"
            ;;
        clean)
            cmd_clean
            ;;
        rebuild)
            cmd_rebuild
            ;;
        test)
            cmd_test
            ;;
        shell)
            cmd_shell "${2:-api}"
            ;;
        db-migrate)
            cmd_db_migrate
            ;;
        help|--help|-h)
            cmd_help
            ;;
        *)
            log_error "Unknown command: $command"
            echo ""
            cmd_help
            exit 1
            ;;
    esac
}

main "$@"
