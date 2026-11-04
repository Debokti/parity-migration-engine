#!/usr/bin/env bash
set -e

echo "================================================================="
echo "  PARITY ENGINE: DETERMINISTIC 6-SCENARIO VERIFICATION (699 CHECKS)"
echo "================================================================="

for i in {1..6}; do
    python3 parity-engine/parity_cli.py verify --scenario "scenario_${i}"
done

echo ""
echo "================================================================="
echo "  PARITY ENGINE: ARTIFACT-GROUNDED ARCHITECTURE Q&A (META MUSE)"
echo "================================================================="

python3 parity-engine/parity_cli.py ask "Explain the 4-eyes principle and how it works"

