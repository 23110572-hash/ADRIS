"""Create the ADRIS v1 normalized domain schema.

Revision ID: 20260718_0001
Revises: None
Create Date: 2026-07-18
"""

from collections.abc import Sequence

from alembic import op

from app.db.base import Base
from app.db import models  # noqa: F401

revision: str = "20260718_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # checkfirst=False makes this migration work in Alembic offline SQL mode as well as on Neon.
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=False)
    op.execute(
        """
        INSERT INTO roles (id, name, description, status, created_at, updated_at, correlation_id)
        VALUES
          ('10000000-0000-4000-8000-000000000001', 'CITIZEN', 'Citizen account owner', 'ACTIVE', now(), now(), '11000000-0000-4000-8000-000000000001'),
          ('10000000-0000-4000-8000-000000000002', 'ANALYST', 'Fraud review analyst', 'ACTIVE', now(), now(), '11000000-0000-4000-8000-000000000002'),
          ('10000000-0000-4000-8000-000000000003', 'SUPERVISOR', 'Review supervisor', 'ACTIVE', now(), now(), '11000000-0000-4000-8000-000000000003'),
          ('10000000-0000-4000-8000-000000000004', 'EVIDENCE_OFFICER', 'Evidence package officer', 'ACTIVE', now(), now(), '11000000-0000-4000-8000-000000000004'),
          ('10000000-0000-4000-8000-000000000005', 'ADMIN', 'ADRIS administrator', 'ACTIVE', now(), now(), '11000000-0000-4000-8000-000000000005')
        """
    )
    op.execute(
        """
        INSERT INTO partners (
          id, name, partner_type, status, adapter_status, capabilities_version, capabilities,
          created_at, updated_at, correlation_id
        ) VALUES
          ('20000000-0000-4000-8000-000000000001', 'Future authorised bank adapter', 'BANK', 'FUTURE_ADAPTER', 'NOT_CONFIGURED', 'partner-v1', '{"live": false}'::jsonb, now(), now(), gen_random_uuid()),
          ('20000000-0000-4000-8000-000000000002', 'Future authorised telecom adapter', 'TELECOM', 'FUTURE_ADAPTER', 'NOT_CONFIGURED', 'partner-v1', '{"live": false}'::jsonb, now(), now(), gen_random_uuid()),
          ('20000000-0000-4000-8000-000000000003', 'Future authorised government adapter', 'GOVERNMENT', 'FUTURE_ADAPTER', 'NOT_CONFIGURED', 'partner-v1', '{"live": false}'::jsonb, now(), now(), gen_random_uuid())
        """
    )


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind(), checkfirst=False)
