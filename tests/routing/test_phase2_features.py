"""Tests for model routing Phase 2a non-security features.

1. Ollama model configurable via settings
2. neut settings edit command
3. VPN auto-detect (already existed, improved to check all providers)
4. Routing decision audit log
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

# ---------------------------------------------------------------------------
# 1. Ollama model configurable
# ---------------------------------------------------------------------------

class TestOllamaModelConfigurable:

    def test_router_reads_ollama_model_from_settings(self):
        """QueryRouter picks up routing.ollama_model from settings."""
        from neutron_os.infra.router import QueryRouter

        with mock.patch(
            "neutron_os.extensions.builtins.settings.store.SettingsStore.get",
            return_value="phi3:mini",
        ):
            router = QueryRouter()
            assert router._ollama._model == "phi3:mini"

    def test_router_falls_back_to_default_model(self):
        """When settings unavailable, use default llama3.2:1b."""
        from neutron_os.infra.router import _OLLAMA_MODEL, QueryRouter

        with mock.patch(
            "neutron_os.infra.router.QueryRouter._default_ollama",
        ) as mock_factory:
            from neutron_os.infra.router import OllamaClassifier
            mock_factory.return_value = OllamaClassifier(model=_OLLAMA_MODEL)
            router = QueryRouter()
            assert router._ollama._model == _OLLAMA_MODEL

    def test_ollama_model_in_settings_defaults(self):
        """routing.ollama_model is registered in settings defaults."""
        from neutron_os.extensions.builtins.settings.store import _DEFAULTS
        assert "routing.ollama_model" in _DEFAULTS
        assert _DEFAULTS["routing.ollama_model"] == "llama3.2:1b"


# ---------------------------------------------------------------------------
# 2. neut settings edit
# ---------------------------------------------------------------------------

class TestSettingsEdit:

    def test_edit_subcommand_registered(self):
        """Parser recognizes 'edit' subcommand."""
        from neutron_os.extensions.builtins.settings.cli import get_parser
        parser = get_parser()
        args = parser.parse_args(["edit"])
        assert args.cmd == "edit"

    def test_edit_uses_editor_env(self):
        """Edit respects $EDITOR environment variable."""
        # Just verify the settings CLI code references EDITOR/VISUAL
        import inspect

        from neutron_os.extensions.builtins.settings import cli
        source = inspect.getsource(cli.main)
        assert "EDITOR" in source


# ---------------------------------------------------------------------------
# 3. VPN auto-detect
# ---------------------------------------------------------------------------

class TestVpnAutoDetect:

    def test_startup_checks_all_vpn_providers(self):
        """_print_model_status checks all VPN providers, not just the first."""
        from neutron_os.extensions.builtins.neut_agent.cli import _print_model_status

        mock_provider1 = mock.MagicMock()
        mock_provider1.name = "anthropic"
        mock_provider1.model = "claude-sonnet"
        mock_provider1.routing_tier = "public"
        mock_provider1.requires_vpn = False

        mock_vpn1 = mock.MagicMock()
        mock_vpn1.name = "qwen-rascal"
        mock_vpn1.requires_vpn = True

        mock_vpn2 = mock.MagicMock()
        mock_vpn2.name = "qwen-tacc"
        mock_vpn2.requires_vpn = True

        mock_gateway = mock.MagicMock()
        mock_gateway.active_provider = mock_provider1
        mock_gateway.providers = [mock_provider1, mock_vpn1, mock_vpn2]
        mock_gateway._check_vpn.side_effect = [True, False]  # rascal reachable, tacc not

        with mock.patch("builtins.print") as mock_print:
            _print_model_status(mock_gateway)

        # Should have checked both VPN providers
        assert mock_gateway._check_vpn.call_count == 2
        printed = " ".join(str(c) for c in mock_print.call_args_list)
        assert "qwen-rascal" in printed
        assert "qwen-tacc" in printed


# ---------------------------------------------------------------------------
# 4. Routing decision audit log
# ---------------------------------------------------------------------------

class TestRoutingAuditLog:

    def test_log_routing_decision_writes_jsonl(self, tmp_path: Path):
        """Audit log writes valid JSONL entries."""
        audit_path = tmp_path / "routing_audit.jsonl"

        with mock.patch(
            "neutron_os.infra.routing_audit._AUDIT_PATH", audit_path,
        ):
            from neutron_os.infra.routing_audit import log_routing_decision

            log_routing_decision(
                session_id="abc123",
                query_hash="deadbeef",
                tier="export_controlled",
                classifier="keyword",
                provider="qwen-rascal",
                matched_terms=["MCNP", "SCALE"],
                reason="export-control keyword match",
            )

        assert audit_path.exists()
        entry = json.loads(audit_path.read_text().strip())
        assert entry["tier"] == "export_controlled"
        assert entry["classifier"] == "keyword"
        assert entry["session_id"] == "abc123"
        assert entry["matched_terms"] == ["MCNP", "SCALE"]
        assert "timestamp" in entry

    def test_log_appends(self, tmp_path: Path):
        """Multiple decisions append to the same file."""
        audit_path = tmp_path / "routing_audit.jsonl"

        with mock.patch(
            "neutron_os.infra.routing_audit._AUDIT_PATH", audit_path,
        ):
            from neutron_os.infra.routing_audit import log_routing_decision

            for i in range(3):
                log_routing_decision(
                    tier="public",
                    classifier="fallback",
                    reason=f"decision {i}",
                )

        lines = audit_path.read_text().strip().splitlines()
        assert len(lines) == 3

    def test_no_plaintext_in_log(self, tmp_path: Path):
        """Audit log contains hash, not plaintext query."""
        audit_path = tmp_path / "routing_audit.jsonl"

        with mock.patch(
            "neutron_os.infra.routing_audit._AUDIT_PATH", audit_path,
        ):
            from neutron_os.infra.routing_audit import hash_query, log_routing_decision

            query = "How do I configure MCNP geometry cards?"
            qhash = hash_query(query)

            log_routing_decision(
                query_hash=qhash,
                tier="export_controlled",
                classifier="keyword",
            )

        content = audit_path.read_text()
        assert query not in content  # no plaintext
        assert qhash in content  # hash present

    def test_hash_query_deterministic(self):
        from neutron_os.infra.routing_audit import hash_query
        h1 = hash_query("test query")
        h2 = hash_query("test query")
        assert h1 == h2
        assert len(h1) == 16  # truncated SHA-256

    def test_hash_query_different_inputs(self):
        from neutron_os.infra.routing_audit import hash_query
        assert hash_query("hello") != hash_query("world")

    def test_disabled_via_settings(self, tmp_path: Path):
        """When routing.audit_log is false, nothing is written."""
        audit_path = tmp_path / "routing_audit.jsonl"

        with mock.patch(
            "neutron_os.infra.routing_audit._AUDIT_PATH", audit_path,
        ), mock.patch(
            "neutron_os.extensions.builtins.settings.store.SettingsStore.get",
            return_value=False,
        ):
            from neutron_os.infra.routing_audit import log_routing_decision

            log_routing_decision(
                tier="public",
                classifier="fallback",
            )

        assert not audit_path.exists()

    def test_audit_log_setting_in_defaults(self):
        """routing.audit_log is registered in settings defaults."""
        from neutron_os.extensions.builtins.settings.store import _DEFAULTS
        assert "routing.audit_log" in _DEFAULTS
        assert _DEFAULTS["routing.audit_log"] is True
