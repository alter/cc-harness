python3 tasks/check.py >/dev/null || { python3 tasks/check.py; echo "check.py rejects the tree /task wrote"; exit 1; }
grep -l '^format:2' tasks/10-build/*/labels.txt >/dev/null 2>&1 || { echo "no format:2 task written"; exit 1; }
grep -hE '^ *sink .*consumes' tasks/10-build/*/task.txt | grep -q . || { echo "the HTML page is a sink but no SECURITY sink line was written"; exit 1; }
n=$(ls -d tasks/10-build/*/ 2>/dev/null | wc -l | tr -d ' ')
[ "$n" -ge 2 ] || { echo "add, list and render are separable parts, but $n task was written"; exit 1; }
