#!/usr/bin/env bash
# Run every pmcp jobs smoke test. Exit non-zero if any test fails.
set -u
cd "$(dirname "$0")"

TESTS=(test_empty.sh test_basic.sh test_corrupted.sh test_missing_fields.sh test_limit.sh)
FAILED=0
for t in "${TESTS[@]}"; do
    if bash "$t"; then
        :
    else
        FAILED=$((FAILED + 1))
    fi
done

echo
if [ $FAILED -eq 0 ]; then
    echo "All ${#TESTS[@]} pmcp jobs smoke tests passed."
    exit 0
else
    echo "$FAILED of ${#TESTS[@]} pmcp jobs smoke tests FAILED."
    exit 1
fi
