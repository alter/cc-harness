---
intake: completed 2026-10-06
---
# PROJECT

## 6. Gate checks

### Fast tier

```
python3 run_tests.py
```

### Full tier

```
#: budget=5m report=reports/junit.xml list="python3 run_tests.py --list"
rm -f state.txt; python3 run_tests.py --junit reports/junit.xml
```

| Question | Answer |
|---|---|
| How a test is marked full-only here | none yet |
| Fast tier wall time at `T00`, seconds, from the run | 3 |
| Full tier budget, minutes, whole run | 5 |
| Audit: run in another order | rm -f state.txt; python3 run_tests.py --reverse --junit reports/junit-reverse.xml |
| Audit: run in parallel | none |

## 7. Delivery
