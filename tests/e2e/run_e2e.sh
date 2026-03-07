#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
docker build -f tests/e2e/Dockerfile -t dictation-e2e .
docker run --rm dictation-e2e
