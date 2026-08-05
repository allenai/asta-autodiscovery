"""Tests for managed Copilot OAuth login output."""

from __future__ import annotations

from types import SimpleNamespace

from utils import copilot_login


def test_login_status_extracts_device_code_and_url(monkeypatch, tmp_path) -> None:
    """Expose the temporary device code that the official CLI prints for the user."""
    output_path = tmp_path / "copilot-login.log"
    output_path.write_text(
        "Open https://github.com/login/device and enter code ABCD-EFGH\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(copilot_login, "_output_path", output_path)
    monkeypatch.setattr(copilot_login, "_process", SimpleNamespace(poll=lambda: None))

    result = copilot_login.status()

    assert result["phase"] == "running"
    assert result["device_code"] == "ABCD-EFGH"
    assert result["verification_url"] == "https://github.com/login/device"


def test_login_uses_autodiscovery_copilot_home(monkeypatch, tmp_path) -> None:
    """Write login state to the same isolated home used by the SDK client."""
    copilot_home = tmp_path / "copilot-home"
    calls = []

    class FakeProcess:
        def poll(self):
            return None

    monkeypatch.setenv("AUTODISCOVERY_COPILOT_HOME", str(copilot_home))
    monkeypatch.setattr(copilot_login, "_process", None)
    monkeypatch.setattr(
        copilot_login.subprocess,
        "Popen",
        lambda command, **kwargs: calls.append((command, kwargs)) or FakeProcess(),
    )

    copilot_login.start("/runtime/copilot", str(tmp_path / "local"))

    assert calls[0][0] == ["/runtime/copilot", "--no-color", "login"]
    assert calls[0][1]["env"]["COPILOT_HOME"] == str(copilot_home)
