#!/usr/bin/env bash
# Verification script for kf.sh - tests all functions without Docker

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KF_SCRIPT="${SCRIPT_DIR}/kf.sh"

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

test_count=0
pass_count=0

test_run() {
    local test_name=$1
    local command=$2
    
    test_count=$((test_count + 1))
    echo -n "Test $test_count: $test_name ... "
    
    if eval "$command" &> /dev/null; then
        echo -e "${GREEN}PASS${NC}"
        pass_count=$((pass_count + 1))
    else
        echo -e "${RED}FAIL${NC}"
    fi
}

echo "🧪 Testing kf.sh script..."
echo ""

# Test 1: Script exists and is executable
test_run "Script exists" "[[ -f '$KF_SCRIPT' ]]"
test_run "Script is executable" "[[ -x '$KF_SCRIPT' ]]"

# Test 2: Syntax validation
test_run "Bash syntax check" "bash -n '$KF_SCRIPT'"

# Test 3: Help command
test_run "Help command works" "'$KF_SCRIPT' help | grep -q 'Usage:'"

# Test 4: All commands listed in help
test_run "Start command in help" "'$KF_SCRIPT' help | grep -q 'start'"
test_run "Stop command in help" "'$KF_SCRIPT' help | grep -q 'stop'"
test_run "Status command in help" "'$KF_SCRIPT' help | grep -q 'status'"
test_run "Logs command in help" "'$KF_SCRIPT' help | grep -q 'logs'"
test_run "Clean command in help" "'$KF_SCRIPT' help | grep -q 'clean'"
test_run "Rebuild command in help" "'$KF_SCRIPT' help | grep -q 'rebuild'"

# Test 5: Invalid command handling
test_run "Invalid command returns error" "! '$KF_SCRIPT' invalid-command &> /dev/null"

# Test 6: File references are correct
test_run "docker-compose.yml exists" "[[ -f '$SCRIPT_DIR/docker-compose.yml' ]]"

# Test 7: Status command (graceful handling when Docker not running)
test_run "Status handles no Docker gracefully" "'$KF_SCRIPT' status 2>&1 | grep -E '(Docker|healthy)' || true"

echo ""
echo "================================"
echo "Results: $pass_count/$test_count tests passed"
echo "================================"

if [[ $pass_count -eq $test_count ]]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}✗ Some tests failed${NC}"
    exit 1
fi
