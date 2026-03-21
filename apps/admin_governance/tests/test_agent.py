"""Tests for TenantAgent and ComplianceAgent."""

from __future__ import annotations

import pytest

from apps.admin_governance.agent import ComplianceAgent, TenantAgent
from shared.event_bus import EventBus
from shared.llm_gateway import LLMGateway
from shared.schemas.base_event import TenantContext

# ── TenantAgent tests ──


@pytest.mark.asyncio
async def test_tenant_agent_list(mock_llm: LLMGateway, event_bus: EventBus):
    agent = TenantAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1", role="admin")
    await event_bus.start()
    result = await agent.run(ctx, input_data={"action_type": "list"})
    await event_bus.stop()
    assert result["decision"]["action"] == "list_tenants"


@pytest.mark.asyncio
async def test_tenant_agent_unauthorized(mock_llm: LLMGateway, event_bus: EventBus):
    """Non-admin should be rejected."""
    agent = TenantAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1", role="viewer")
    await event_bus.start()
    result = await agent.run(ctx, input_data={"action_type": "list"})
    await event_bus.stop()
    assert result["decision"]["action"] == "unauthorized"


@pytest.mark.asyncio
async def test_tenant_agent_create(mock_llm: LLMGateway, event_bus: EventBus):
    agent = TenantAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1", role="admin")
    await event_bus.start()
    result = await agent.run(ctx, input_data={"action_type": "create"})
    await event_bus.stop()
    assert result["decision"]["action"] == "create_tenant"


@pytest.mark.asyncio
async def test_tenant_agent_delete(mock_llm: LLMGateway, event_bus: EventBus):
    agent = TenantAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1", role="admin")
    await event_bus.start()
    result = await agent.run(ctx, input_data={"action_type": "delete"})
    await event_bus.stop()
    assert result["decision"]["action"] == "delete_tenant"


@pytest.mark.asyncio
async def test_tenant_agent_rotate_key(mock_llm: LLMGateway, event_bus: EventBus):
    agent = TenantAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1", role="admin")
    await event_bus.start()
    result = await agent.run(ctx, input_data={"action_type": "rotate_key"})
    await event_bus.stop()
    assert result["decision"]["action"] == "rotate_api_key"


@pytest.mark.asyncio
async def test_tenant_agent_export_audit(mock_llm: LLMGateway, event_bus: EventBus):
    agent = TenantAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1", role="admin")
    await event_bus.start()
    result = await agent.run(ctx, input_data={"action_type": "export_audit"})
    await event_bus.stop()
    assert result["decision"]["action"] == "export_audit_log"


@pytest.mark.asyncio
async def test_tenant_agent_uses_haiku(mock_llm: LLMGateway, event_bus: EventBus):
    agent = TenantAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1", role="admin")
    await event_bus.start()
    await agent.run(ctx, input_data={"action_type": "list"})
    await event_bus.stop()
    call_kwargs = mock_llm._anthropic.messages.create.call_args
    assert "haiku" in call_kwargs.kwargs.get("model", "")


# ── ComplianceAgent tests ──


@pytest.mark.asyncio
async def test_compliance_report(mock_llm: LLMGateway, event_bus: EventBus):
    agent = ComplianceAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    input_data = {"total_decisions": 200, "high_risk_count": 10, "approval_rate": 95.0}
    await event_bus.start()
    result = await agent.run(ctx, input_data=input_data)
    await event_bus.stop()
    assert result["decision"]["action"] == "compliance_report"
    assert result["decision"]["has_violations"] is False


@pytest.mark.asyncio
async def test_compliance_with_violations(mock_llm: LLMGateway, event_bus: EventBus):
    agent = ComplianceAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    input_data = {"total_decisions": 100, "high_risk_count": 20, "approval_rate": 80.0}
    await event_bus.start()
    result = await agent.run(ctx, input_data=input_data)
    await event_bus.stop()
    assert result["decision"]["has_violations"] is True


@pytest.mark.asyncio
async def test_compliance_uses_sonnet(mock_llm: LLMGateway, event_bus: EventBus):
    agent = ComplianceAgent(llm_gateway=mock_llm, event_bus=event_bus)
    ctx = TenantContext(tenant_id="t1")
    await event_bus.start()
    await agent.run(ctx, input_data={})
    await event_bus.stop()
    call_kwargs = mock_llm._anthropic.messages.create.call_args
    assert "sonnet" in call_kwargs.kwargs.get("model", "")
