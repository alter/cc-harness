p=docs/plans/p.md
grep -qiE '^- \[ \] T0?1a? .*(upper|case)' $p || grep -qiE '^- \[ \] T[0-9]+[a-z]? .*(upper|case)' $p || { echo "no fix task for the reproduced currency finding"; exit 1; }
grep -iE '^- \[ \] T[0-9]+[a-z]? .*decimal' $p && { echo "a fix task was added for a directive that contradicts D1"; exit 1; }
awk '/^## Assumptions/{a=1;next} /^## /{a=0} a' $p | grep -qiE 'D1' || { echo "the D1 conflict is not recorded under Assumptions"; exit 1; }
grep -iE '^- \[ \] T[0-9]+[a-z]? .*(slow|performance)' $p && { echo "a PLAUSIBLE finding became a task"; exit 1; }
exit 0
