"""pytest configuration for usdagent tests.

Sets USDAGENT_LLM=0 so that generator tests use the fast deterministic
fallback path rather than calling ollama. This makes tests runnable
without a local LLM and keeps them fast and reproducible in CI.
"""
import os
import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Disable LLM before any test collection or imports."""
    os.environ.setdefault("USDAGENT_LLM", "0")
