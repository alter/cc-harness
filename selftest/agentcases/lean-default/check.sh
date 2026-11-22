# check.sh
grep -rqs --include='*.py' 'split_fee' tests/ || { echo "no test names split_fee: the money function was left without a test"; exit 1; }
if grep -rqs --include='*.py' 'export_report' tests/; then echo "a test names export_report: glue got a test at the smallest level"; exit 1; fi
python3 -m unittest discover -s tests >/dev/null 2>&1 || { echo "the tests do not pass"; exit 1; }
