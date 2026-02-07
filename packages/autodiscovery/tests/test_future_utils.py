from concurrent.futures import ThreadPoolExecutor

from autodiscovery.future_utils import gather_completed_futures


def test_gather_completed_futures_continues_after_exception():
    labels = {}
    errors = []

    with ThreadPoolExecutor(max_workers=2) as executor:
        ok_future = executor.submit(lambda: "ok")
        bad_future = executor.submit(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        labels[ok_future] = "node_1_0"
        labels[bad_future] = "node_1_1"

        results = gather_completed_futures(
            labels,
            on_error=lambda label, exc: errors.append((label, type(exc).__name__, str(exc))),
        )

    assert results == ["ok"]
    assert errors == [("node_1_1", "RuntimeError", "boom")]
