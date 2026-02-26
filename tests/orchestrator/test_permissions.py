"""Tests for the permission store — session and global approval memory."""

import json
import pytest
from pathlib import Path

from tools.agents.orchestrator.permissions import (
    PermissionStore,
    PermissionRule,
    PermissionScope,
)


class TestPermissionStore:
    """Test permission CRUD, persistence, and scope logic."""

    @pytest.fixture
    def perms(self, tmp_path):
        """Create a PermissionStore with a temp permissions file."""
        return PermissionStore(permissions_file=tmp_path / "permissions.json")

    def test_empty_store(self, perms):
        assert perms.is_allowed("doc_publish") is False
        assert perms.list_rules() == []

    def test_allow_session(self, perms):
        perms.allow_session("doc_publish")
        assert perms.is_allowed("doc_publish") is True

    def test_session_rule_not_persisted(self, perms, tmp_path):
        perms.allow_session("doc_publish")
        # Create a new store from same file — session rules lost
        perms2 = PermissionStore(permissions_file=tmp_path / "permissions.json")
        assert perms2.is_allowed("doc_publish") is False

    def test_allow_global(self, perms, tmp_path):
        perms.allow_global("doc_publish")
        assert perms.is_allowed("doc_publish") is True
        # Verify persisted
        perms2 = PermissionStore(permissions_file=tmp_path / "permissions.json")
        assert perms2.is_allowed("doc_publish") is True

    def test_session_overrides_global(self, perms):
        perms.allow_global("doc_publish")
        assert perms.is_allowed("doc_publish") is True
        # Revoking from session shouldn't affect global
        # But a session rule with allowed=False would override
        perms._session_rules["doc_publish"] = PermissionRule(
            tool_name="doc_publish",
            scope=PermissionScope.SESSION,
            allowed=False,
        )
        assert perms.is_allowed("doc_publish") is False

    def test_revoke(self, perms):
        perms.allow_session("doc_publish")
        perms.allow_global("sense_ingest")
        perms.revoke("doc_publish")
        perms.revoke("sense_ingest")
        assert perms.is_allowed("doc_publish") is False
        assert perms.is_allowed("sense_ingest") is False

    def test_reset(self, perms, tmp_path):
        perms.allow_session("doc_publish")
        perms.allow_global("sense_ingest")
        perms.reset()
        assert perms.list_rules() == []
        # Verify global file is cleared
        perms2 = PermissionStore(permissions_file=tmp_path / "permissions.json")
        assert perms2.list_rules() == []

    def test_list_rules(self, perms):
        perms.allow_session("doc_publish")
        perms.allow_global("sense_ingest")
        rules = perms.list_rules()
        assert len(rules) == 2
        names = {r.tool_name for r in rules}
        assert "doc_publish" in names
        assert "sense_ingest" in names

    def test_list_rules_session_overrides(self, perms):
        perms.allow_global("doc_publish")
        perms.allow_session("doc_publish")
        rules = perms.list_rules()
        # Should show session scope (overrides global)
        assert len(rules) == 1
        assert rules[0].scope == PermissionScope.SESSION

    def test_clear_session(self, perms):
        perms.allow_session("doc_publish")
        perms.allow_global("sense_ingest")
        perms.clear_session()
        assert perms.is_allowed("doc_publish") is False
        assert perms.is_allowed("sense_ingest") is True

    def test_persistence_format(self, perms, tmp_path):
        perms.allow_global("doc_publish")
        perms.allow_global("sense_ingest")
        data = json.loads((tmp_path / "permissions.json").read_text())
        assert "rules" in data
        assert len(data["rules"]) == 2

    def test_corrupted_file_handled(self, tmp_path):
        pfile = tmp_path / "permissions.json"
        pfile.write_text("not json!")
        perms = PermissionStore(permissions_file=pfile)
        assert perms.list_rules() == []


class TestPermissionRule:
    """Test PermissionRule serialization."""

    def test_to_dict(self):
        rule = PermissionRule(
            tool_name="doc_publish",
            scope=PermissionScope.GLOBAL,
            allowed=True,
        )
        d = rule.to_dict()
        assert d["tool_name"] == "doc_publish"
        assert d["scope"] == "global"
        assert d["allowed"] is True

    def test_from_dict(self):
        d = {"tool_name": "sense_ingest", "scope": "session", "allowed": True}
        rule = PermissionRule.from_dict(d)
        assert rule.tool_name == "sense_ingest"
        assert rule.scope == PermissionScope.SESSION

    def test_from_dict_defaults(self):
        d = {"tool_name": "test"}
        rule = PermissionRule.from_dict(d)
        assert rule.scope == PermissionScope.SESSION
        assert rule.allowed is True


class TestApprovalGateWithPermissions:
    """Test the ApprovalGate + PermissionStore integration."""

    def test_auto_approve_via_permissions(self, tmp_path):
        from tools.agents.orchestrator.approval import ApprovalGate
        from tools.agents.orchestrator.actions import create_action, ActionStatus

        perms = PermissionStore(permissions_file=tmp_path / "permissions.json")
        perms.allow_session("doc_publish")
        gate = ApprovalGate(permissions=perms)

        action = create_action("doc_publish", {"source": "foo.md"})
        gate.submit(action)
        # Should be auto-approved via permission
        assert action.status == ActionStatus.APPROVED

    def test_no_auto_approve_without_permission(self, tmp_path):
        from tools.agents.orchestrator.approval import ApprovalGate
        from tools.agents.orchestrator.actions import create_action, ActionStatus

        perms = PermissionStore(permissions_file=tmp_path / "permissions.json")
        gate = ApprovalGate(permissions=perms)

        action = create_action("doc_publish", {"source": "foo.md"})
        gate.submit(action)
        assert action.status == ActionStatus.PENDING

    def test_gate_without_permissions_unchanged(self):
        from tools.agents.orchestrator.approval import ApprovalGate
        from tools.agents.orchestrator.actions import create_action, ActionStatus

        gate = ApprovalGate()
        action = create_action("doc_publish")
        gate.submit(action)
        assert action.status == ActionStatus.PENDING

        action2 = create_action("query_docs")
        gate.submit(action2)
        assert action2.status == ActionStatus.APPROVED
