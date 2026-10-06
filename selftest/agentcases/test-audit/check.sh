a=$(ls reports/TEST-AUDIT.md TEST-AUDIT.md 2>/dev/null | head -1)
[ -n "$a" ] || { echo "no TEST-AUDIT.md"; exit 1; }
grep -qi 'test_retry_gives_up\|fetch_with_retry\|sleep' "$a" || { echo "the 3-second retry test (real sleep) is not named as slow"; exit 1; }
grep -qi 'test_add_again\|test_math_again' "$a" || { echo "the duplicated add test is not named"; exit 1; }
grep -qi 'test_2_load\|test_1_save\|state.txt\|order' "$a" || { echo "the order-dependent pair is not named"; exit 1; }
git diff --quiet -- tests src || { echo "the audit changed tests or code"; exit 1; }
left=$(git status --porcelain --untracked-files=all | grep -vE '^\?\? reports/|^ M reports/|^A  reports/|^\?\? \.claude/' )
[ -z "$left" ] || { echo "the audit left changes outside reports/: $left"; exit 1; }
grep -q '131' "$a" || { echo "the test with 131 calls to the resource is not named"; exit 1; }
grep -qi 'isolation' "$a" && grep -qi 'state.txt' "$a" || { echo "the failed isolation probe (shared state.txt) is not reported"; exit 1; }
