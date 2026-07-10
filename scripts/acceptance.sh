#!/usr/bin/env bash
# SCOUT acceptance sequence (PLAN.md §9, checks 1-5).
#
# Run it three consecutive times for the §9.6 stability rule:
#   for i in 1 2 3; do ./scripts/acceptance.sh || exit 1; done
#
# Requires python3.11 and python3.12 on PATH. Uses no live network beyond
# pip installs.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
cd "$ROOT"

step() { printf '\n=== %s ===\n' "$*"; }

step "1. Full pytest suite on Python 3.11 and 3.12"
for py in python3.11 python3.12; do
    "$py" -m venv "$WORK/test-$py"
    "$WORK/test-$py/bin/pip" -q install -e ".[dev]"
    "$WORK/test-$py/bin/pytest" -q
done

step "2. Fresh-venv install (pip install .) + offline scout \"test\" --json"
python3.11 -m venv "$WORK/fresh"
"$WORK/fresh/bin/pip" -q install "$ROOT"
( cd "$WORK" && SCOUT_NO_AUTOCONFIG=1 "$WORK/fresh/bin/scout" "test" --json --offline > "$WORK/response.json" )
"$WORK/fresh/bin/python" - "$WORK/response.json" <<'EOF'
import sys
from scout.schema import SearchResponse
response = SearchResponse.model_validate_json(open(sys.argv[1]).read())
assert response.query == "test" and response.results, "invalid SearchResponse"
print(f"valid SearchResponse: {len(response.results)} results, health={dict(response.health)}")
EOF

PYTEST="$WORK/test-python3.11/bin/pytest"

step "3. Stub end-to-end: 3 ok + 1 timeout + 1 error; dedupe verified"
"$PYTEST" -q \
    tests/test_core.py::test_search_succeeds_when_sources_timeout_and_error \
    tests/test_core.py::test_dedupe_collision_keeps_first_position_and_richer_content \
    tests/test_core.py::test_dedupe_records_all_sources_and_ors_trusted

step "4. searxng_public disabled by default; enabling via config works"
"$PYTEST" -q tests/test_searxng_public.py

step "5. Politeness audit: rate limits, honest UA, robots; no google/bing scraping"
"$PYTEST" -q tests/test_politeness.py \
    "tests/test_engine_adapters.py::test_scraping_engines_declare_politeness" \
    "tests/test_engine_adapters.py::test_no_google_or_bing_endpoints"
if grep -RInE '(google|bing)\.com/search' scout/; then
    echo "FAIL: found a forbidden scraping endpoint" >&2
    exit 1
fi

printf '\nACCEPTANCE RUN PASSED\n'
