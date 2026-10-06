a=$(ls reports/TEST-AUDIT.md TEST-AUDIT.md 2>/dev/null | head -1)
[ -n "$a" ] || { echo "no TEST-AUDIT.md"; exit 1; }
grep -qi 'test_retry_gives_up\|fetch_with_retry\|sleep' "$a" || { echo "the 3-second retry test (real sleep) is not named as slow"; exit 1; }
grep -qi 'test_add_again\|test_math_again' "$a" || { echo "the duplicated add test is not named"; exit 1; }
grep -qi 'test_2_load\|test_1_save\|state.txt\|order' "$a" || { echo "the order-dependent pair is not named"; exit 1; }
git diff --quiet -- tests src || { echo "the audit changed tests or code"; exit 1; }
