python3 -m unittest discover -s tests >/dev/null 2>&1 || { echo "tests do not pass on the main branch after the run"; exit 1; }
[ "$(git log --merges --oneline | wc -l | tr -d ' ')" -ge 2 ] || { echo "the two parts were not merged from their own branches"; exit 1; }
for t in 02-headers 03-body; do grep -q '^status:done' tasks/10-build/$t/labels.txt || { echo "$t is not done"; exit 1; }; done
