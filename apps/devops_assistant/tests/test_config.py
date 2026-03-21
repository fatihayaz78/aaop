"""Tests for DevOps Assistant config."""

from __future__ import annotations

from apps.devops_assistant.config import DevOpsAssistantConfig


def test_defaults():
    cfg = DevOpsAssistantConfig()
    assert cfg.runbook_search_top_k == 3
    assert cfg.deployment_history_limit == 20
    assert cfg.health_check_timeout_ms == 5000
    assert "rm -rf" in cfg.dangerous_commands


def test_custom():
    cfg = DevOpsAssistantConfig(runbook_search_top_k=5, deployment_history_limit=50)
    assert cfg.runbook_search_top_k == 5
    assert cfg.deployment_history_limit == 50
