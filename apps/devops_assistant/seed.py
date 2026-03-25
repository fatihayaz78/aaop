"""Seed for DevOps Assistant — shares runbooks from knowledge_base."""
from __future__ import annotations
import structlog
logger = structlog.get_logger(__name__)

def seed_devops_assistant_mock_data(tenant_id: str = "s_sport_plus") -> None:
    """No additional seeding — DevOps reads from knowledge_base collections."""
    logger.info("devops_seed_noop", tenant_id=tenant_id)
