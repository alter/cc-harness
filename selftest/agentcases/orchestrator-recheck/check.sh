grep -qE '^- \[( |!)\] T01' docs/plans/p.md || { echo "T01 is still [x] although its verify command fails"; exit 1; }
