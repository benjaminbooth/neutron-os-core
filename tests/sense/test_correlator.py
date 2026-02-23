"""Unit tests for the entity correlator."""

import pytest
from tools.agents.sense.correlator import Correlator, Person, Initiative


class TestPersonParsing:
    """Test parsing people.md format."""

    def test_parse_people(self, tmp_config):
        correlator = Correlator(config_dir=tmp_config)
        assert len(correlator.people) == 3

        alice = correlator.people[0]
        assert alice.name == "Alice Smith"
        assert alice.gitlab == "asmith"

    def test_parse_empty_file(self, tmp_path):
        config = tmp_path / "config"
        config.mkdir()
        (config / "people.md").write_text("# Empty\n")
        (config / "initiatives.md").write_text("# Empty\n")

        correlator = Correlator(config_dir=config)
        assert len(correlator.people) == 0

    def test_parse_real_config(self, repo_root):
        """Integration test: parse the actual people.md if it exists."""
        config_dir = repo_root / "tools" / "agents" / "config"
        if not config_dir.exists():
            pytest.skip("No config/ directory")

        correlator = Correlator(config_dir=config_dir)
        assert len(correlator.people) > 0
        # Verify Ben Booth exists
        ben = correlator.match_person("Ben Booth")
        assert ben is not None
        assert ben.gitlab == "bbooth"


class TestInitiativeParsing:
    """Test parsing initiatives.md format."""

    def test_parse_initiatives(self, tmp_config):
        correlator = Correlator(config_dir=tmp_config)
        assert len(correlator.initiatives) == 3

        alpha = correlator.initiatives[0]
        assert alpha.name == "Project Alpha"
        assert alpha.status == "Active"


class TestPersonMatching:
    """Test fuzzy person matching."""

    def test_exact_name_match(self, tmp_config):
        correlator = Correlator(config_dir=tmp_config)
        result = correlator.match_person("Alice Smith")
        assert result is not None
        assert result.name == "Alice Smith"

    def test_first_name_match(self, tmp_config):
        correlator = Correlator(config_dir=tmp_config)
        result = correlator.match_person("Alice")
        assert result is not None
        assert result.name == "Alice Smith"

    def test_last_name_match(self, tmp_config):
        correlator = Correlator(config_dir=tmp_config)
        result = correlator.match_person("Jones")
        assert result is not None
        assert result.name == "Bob Jones"

    def test_gitlab_username_match(self, tmp_config):
        correlator = Correlator(config_dir=tmp_config)
        result = correlator.match_person("asmith")
        assert result is not None
        assert result.name == "Alice Smith"

    def test_linear_username_match(self, tmp_config):
        correlator = Correlator(config_dir=tmp_config)
        result = correlator.match_person("bob.j")
        assert result is not None
        assert result.name == "Bob Jones"

    def test_case_insensitive_match(self, tmp_config):
        correlator = Correlator(config_dir=tmp_config)
        result = correlator.match_person("alice")
        assert result is not None
        assert result.name == "Alice Smith"

    def test_no_match(self, tmp_config):
        correlator = Correlator(config_dir=tmp_config)
        result = correlator.match_person("Unknown Person")
        assert result is None

    def test_empty_string(self, tmp_config):
        correlator = Correlator(config_dir=tmp_config)
        result = correlator.match_person("")
        assert result is None

    def test_resolve_people_list(self, tmp_config):
        correlator = Correlator(config_dir=tmp_config)
        result = correlator.resolve_people(["Alice", "unknown", "bjones"])
        assert result == ["Alice Smith", "unknown", "Bob Jones"]


class TestInitiativeMatching:
    """Test fuzzy initiative matching."""

    def test_exact_name_match(self, tmp_config):
        correlator = Correlator(config_dir=tmp_config)
        result = correlator.match_initiative("Project Alpha")
        assert result is not None
        assert result.name == "Project Alpha"

    def test_partial_name_match(self, tmp_config):
        correlator = Correlator(config_dir=tmp_config)
        result = correlator.match_initiative("Alpha")
        assert result is not None
        assert result.name == "Project Alpha"

    def test_repo_path_match(self, tmp_config):
        correlator = Correlator(config_dir=tmp_config)
        result = correlator.match_initiative("alpha_project")
        assert result is not None
        assert result.name == "Project Alpha"

    def test_case_insensitive(self, tmp_config):
        correlator = Correlator(config_dir=tmp_config)
        result = correlator.match_initiative("project beta")
        assert result is not None
        assert result.name == "Project Beta"

    def test_no_match(self, tmp_config):
        correlator = Correlator(config_dir=tmp_config)
        result = correlator.match_initiative("Nonexistent Project")
        assert result is None

    def test_resolve_initiatives_list(self, tmp_config):
        correlator = Correlator(config_dir=tmp_config)
        result = correlator.resolve_initiatives(["Alpha", "unknown"])
        assert result == ["Project Alpha", "unknown"]
