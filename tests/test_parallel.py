import threading
import time

import pytest

from insights.parallel import concurrently


def test_results_keep_the_order_of_their_inputs_even_when_later_items_finish_first():
    def slow_for_small(number: int) -> int:
        time.sleep(0.05 if number == 0 else 0)
        return number * 10

    assert concurrently(slow_for_small, range(5)) == [0, 10, 20, 30, 40]


def test_work_really_overlaps():
    started = threading.Barrier(3, timeout=2)
    assert concurrently(lambda _: started.wait() >= 0, range(3), workers=3) == [True, True, True]


def test_a_failure_in_any_item_surfaces():
    def fails_on_two(number: int) -> int:
        if number == 2:
            raise ValueError("two")
        return number

    with pytest.raises(ValueError, match="two"):
        concurrently(fails_on_two, range(4))


def test_no_items_means_no_results():
    assert concurrently(str, []) == []
