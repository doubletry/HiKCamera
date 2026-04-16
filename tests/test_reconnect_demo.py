from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_reconnect_demo_module():
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "demos" / "reconnect.py"
    spec = importlib.util.spec_from_file_location("demo_reconnect", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_record_retry_failure_is_unlimited_when_max_retries_is_zero() -> None:
    module = _load_reconnect_demo_module()

    retries, exceeded = module.record_retry_failure(0, 0)

    assert retries == 0
    assert exceeded is False


def test_record_retry_failure_counts_and_detects_exhaustion() -> None:
    module = _load_reconnect_demo_module()

    retries, exceeded = module.record_retry_failure(1, 2)
    assert retries == 2
    assert exceeded is False

    retries, exceeded = module.record_retry_failure(retries, 2)
    assert retries == 3
    assert exceeded is True


def test_next_retry_attempt_label_matches_retry_mode() -> None:
    module = _load_reconnect_demo_module()

    assert module.next_retry_attempt_label(0, 0) == "unlimited"
    assert module.next_retry_attempt_label(0, 3) == "1"
    assert module.next_retry_attempt_label(2, 3) == "3"
