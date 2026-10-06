# calls_per_test.py
COUNTS = {
    "tests.test_math.Add::test_add": 131,
    "tests.test_math_again.AddAgain::test_add_again": 4,
    "tests.test_order.Order::test_1_save": 2,
    "tests.test_order.Order::test_2_load": 1,
    "tests.test_retry.Retry::test_retry_gives_up": 3,
}
for test, n in COUNTS.items():
    print(test, n)
