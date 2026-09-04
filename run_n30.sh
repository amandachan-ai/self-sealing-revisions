#!/bin/bash
set -u
cd "$(dirname "$0")"
PY=.venv/bin/python
COMMON="--model claude-sonnet-5 --effort high -n 30 --quiet --jsonl logs/n30.jsonl"
echo "### natural  $(date +%T)"
$PY -m selfsealing.smoke $COMMON --arm natural            > logs/n30_natural.txt 2>&1
echo "### broad    $(date +%T)"
$PY -m selfsealing.smoke $COMMON --arm broad --inject-broad > logs/n30_broad.txt 2>&1
echo "### done     $(date +%T)"
