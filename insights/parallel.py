"""Runs independent network-bound work side by side. Results keep the order of their inputs."""

from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor

default_workers = 4


def concurrently[Item, Result](work: Callable[[Item], Result], items: Iterable[Item], workers: int = default_workers) -> list[Result]:
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(work, items))
