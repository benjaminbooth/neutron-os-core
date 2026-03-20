"""Add audit log tables: routing_events, classification_events, vpn_events, config_load_events.

Revision ID: 20260319_audit_log
Revises:
Create Date: 2026-03-19

These tables implement the EC Compliance Audit Log (Layer 2) described in
docs/tech-specs/spec-logging.md §8. The HMAC chain on routing_events provides
tamper-evident audit records per 10 CFR 810 internal policy.

Row Level Security (Phase 2 — not yet applied):
    After enabling RLS on each table, add policies such as:

        ALTER TABLE routing_events ENABLE ROW LEVEL SECURITY;
        CREATE POLICY audit_read_own ON routing_events
            FOR SELECT USING (session_id = current_setting('app.session_id'));

        -- Privileged compliance role bypasses row filter:
        CREATE POLICY audit_read_compliance ON routing_events
            FOR SELECT TO compliance_auditor USING (TRUE);

    Equivalent policies should be mirrored on classification_events,
    vpn_events, and config_load_events keyed to their routing_event_id FK.
    Phase 2 enablement must be coordinated with the application connection
    pool to ensure `app.session_id` is set on every connection before queries.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260319_audit_log"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # routing_events
    # Central audit spine — every LLM routing decision produces one row.
    # The hmac column carries an HMAC-SHA256 over
    # (event_id || session_id || ts || prompt_hash) keyed with a secret
    # held outside the database, enabling offline tamper detection.
    # ------------------------------------------------------------------
    op.create_table(
        "routing_events",
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column(
            "ts",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("classifier", sa.Text(), nullable=False),
        sa.Column("tier_requested", sa.Text(), nullable=False),
        sa.Column("tier_assigned", sa.Text(), nullable=False),
        sa.Column("provider_name", sa.Text(), nullable=False),
        sa.Column("provider_tier", sa.Text(), nullable=False),
        sa.Column("blocked", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("block_reason", sa.Text(), nullable=True),
        sa.Column("ec_violation", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("prompt_hash", sa.Text(), nullable=False),
        sa.Column("response_hash", sa.Text(), nullable=True),
        sa.Column("is_ec", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("hmac", sa.Text(), nullable=False),
    )

    # Index on ts for time-range queries (log tailing, retention sweeps).
    op.create_index(
        "ix_routing_events_ts",
        "routing_events",
        ["ts"],
    )

    # Partial index — only rows that represent actual EC violations.
    # Keeps compliance dashboards fast without scanning non-violation rows.
    op.create_index(
        "ix_routing_events_ec_violation",
        "routing_events",
        ["ec_violation"],
        postgresql_where=sa.text("ec_violation = TRUE"),
    )

    # ------------------------------------------------------------------
    # classification_events
    # One row per classification pass executed for a routing decision.
    # Linked back to routing_events via routing_event_id (nullable to
    # allow standalone classification diagnostics in test harnesses).
    # ------------------------------------------------------------------
    op.create_table(
        "classification_events",
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("routing_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "ts",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("keyword_matched", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("keyword_term", sa.Text(), nullable=True),
        sa.Column("ollama_result", sa.Text(), nullable=True),
        sa.Column(
            "sensitivity",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'standard'"),
        ),
        sa.Column("final_tier", sa.Text(), nullable=False),
        sa.Column("prompt_hash", sa.Text(), nullable=False),
        sa.Column("is_ec", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.ForeignKeyConstraint(
            ["routing_event_id"],
            ["routing_events.event_id"],
            name="fk_classification_events_routing_event_id",
        ),
    )

    # ------------------------------------------------------------------
    # vpn_events
    # Records each VPN reachability probe performed before routing to an
    # EC-tier provider. check_duration_ms supports latency SLO tracking.
    # ------------------------------------------------------------------
    op.create_table(
        "vpn_events",
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("routing_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "ts",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("provider_name", sa.Text(), nullable=False),
        sa.Column("vpn_reachable", sa.Boolean(), nullable=False),
        sa.Column("check_duration_ms", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["routing_event_id"],
            ["routing_events.event_id"],
            name="fk_vpn_events_routing_event_id",
        ),
    )

    # ------------------------------------------------------------------
    # config_load_events
    # Written once at daemon startup (and on SIGHUP reload) to capture
    # the provider configuration state. providers_json stores the full
    # sanitised provider list (secrets stripped before insert).
    # ------------------------------------------------------------------
    op.create_table(
        "config_load_events",
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "ts",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("config_file", sa.Text(), nullable=False),
        sa.Column("providers_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("ec_providers_count", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    # Drop in reverse dependency order so FK constraints are satisfied.
    op.drop_table("config_load_events")
    op.drop_index("ix_routing_events_ec_violation", table_name="routing_events")
    op.drop_index("ix_routing_events_ts", table_name="routing_events")
    op.drop_table("vpn_events")
    op.drop_table("classification_events")
    op.drop_table("routing_events")
