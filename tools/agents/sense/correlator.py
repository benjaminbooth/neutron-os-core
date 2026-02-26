"""Entity resolution for neut sense.

Maps fuzzy mentions of people and initiatives to known entities loaded
from config/people.md and config/initiatives.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Config directory: tools/agents/config/ (gitignored, real data)
# Falls back to tools/agents/config.example/ if config/ doesn't exist
_AGENTS_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = _AGENTS_DIR / "config"
CONFIG_EXAMPLE_DIR = _AGENTS_DIR / "config.example"


@dataclass
class Person:
    name: str
    aliases: list[str] = field(default_factory=list)  # Nicknames, phonetic variants
    gitlab: str = ""
    role: str = ""
    initiatives: list[str] = field(default_factory=list)
    # Derived: lowercase first name, last name, full name, aliases for matching
    _match_keys: list[str] = field(default_factory=list, repr=False)

    def __post_init__(self):
        parts = self.name.split()
        keys = [self.name.lower()]
        if parts:
            keys.append(parts[0].lower())  # first name
            if len(parts) > 1:
                keys.append(parts[-1].lower())  # last name
        if self.gitlab and self.gitlab != "—":
            # Handle comma-separated gitlab usernames
            for username in self.gitlab.split(","):
                username = username.strip()
                if username:
                    keys.append(username.lower())
        # Add all aliases as match keys (critical for STT correction)
        for alias in self.aliases:
            alias_lower = alias.lower().strip()
            if alias_lower and alias_lower not in keys:
                keys.append(alias_lower)
        self._match_keys = keys


@dataclass
class Initiative:
    id: str
    name: str
    status: str = "Active"
    owners: list[str] = field(default_factory=list)
    gitlab_repos: list[str] = field(default_factory=list)
    # Derived keywords for fuzzy matching
    _match_keys: list[str] = field(default_factory=list, repr=False)

    def __post_init__(self):
        keys = [self.name.lower()]
        # Split name into words for partial matching
        for word in self.name.lower().split():
            if len(word) > 2:
                keys.append(word)
        # Add repo path fragments
        for repo in self.gitlab_repos:
            keys.append(repo.lower().replace("*", "").strip("/"))
        self._match_keys = keys


class Correlator:
    """Loads people and initiatives from config, provides fuzzy matching."""

    def __init__(self, config_dir: Optional[Path] = None):
        if config_dir is None:
            config_dir = CONFIG_DIR if CONFIG_DIR.exists() else CONFIG_EXAMPLE_DIR
        self.config_dir = config_dir
        self.people: list[Person] = []
        self.initiatives: list[Initiative] = []
        self._load()

    def _load(self):
        people_path = self.config_dir / "people.md"
        if people_path.exists():
            self.people = self._parse_people(people_path.read_text())

        init_path = self.config_dir / "initiatives.md"
        if init_path.exists():
            self.initiatives = self._parse_initiatives(init_path.read_text())

    @staticmethod
    def _parse_people(text: str) -> list[Person]:
        """Parse a markdown table of people."""
        people = []
        lines = text.strip().splitlines()
        in_table = False
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "|" not in line:
                continue
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if not cells or len(cells) < 2:
                continue
            # Skip header row and separator
            if cells[0].lower() == "name" or set(cells[0]) <= {"-", " ", ":"}:
                in_table = True
                continue
            if set(cells[0]) <= {"-", " ", ":"}:
                continue
            if not in_table:
                # First data row starts the table
                in_table = True
                if cells[0].lower() == "name":
                    continue

            # Parse table: Name | Aliases | GitLab | Role | Initiative(s)
            name = cells[0] if len(cells) > 0 else ""
            aliases_str = cells[1] if len(cells) > 1 else ""
            gitlab = cells[2] if len(cells) > 2 else ""
            role = cells[3] if len(cells) > 3 else ""
            initiatives_str = cells[4] if len(cells) > 4 else ""

            # Parse aliases (comma-separated)
            aliases = [a.strip() for a in aliases_str.split(",") if a.strip() and a.strip() != "—"]
            initiatives = [i.strip() for i in initiatives_str.split(",") if i.strip()]

            if name and name != "Name":
                people.append(Person(
                    name=name,
                    aliases=aliases,
                    gitlab=gitlab if gitlab != "—" else "",
                    role=role,
                    initiatives=initiatives,
                ))
        return people

    @staticmethod
    def _parse_initiatives(text: str) -> list[Initiative]:
        """Parse a markdown table of initiatives."""
        initiatives = []
        lines = text.strip().splitlines()
        in_table = False
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "|" not in line:
                continue
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if not cells or len(cells) < 2:
                continue
            if cells[0].lower() == "id" or set(cells[0]) <= {"-", " ", ":"}:
                in_table = True
                continue
            if set(cells[0]) <= {"-", " ", ":"}:
                continue
            if not in_table:
                in_table = True
                if cells[0].lower() == "id":
                    continue

            init_id = cells[0] if len(cells) > 0 else ""
            name = cells[1] if len(cells) > 1 else ""
            status = cells[2] if len(cells) > 2 else "Active"
            owners_str = cells[3] if len(cells) > 3 else ""
            repos_str = cells[4] if len(cells) > 4 else ""

            owners = [o.strip() for o in owners_str.split(",") if o.strip()]
            repos = [r.strip() for r in repos_str.split(",") if r.strip()]

            if name:
                initiatives.append(Initiative(
                    id=init_id,
                    name=name,
                    status=status,
                    owners=owners,
                    gitlab_repos=repos,
                ))
        return initiatives

    def match_person(self, mention: str) -> Optional[Person]:
        """Fuzzy-match a text mention to a known person.

        Handles partial names like "Cole" → "Cole Gentry",
        GitLab usernames like "cgentry7" → "Cole Gentry", etc.
        """
        mention_lower = mention.lower().strip()
        if not mention_lower:
            return None

        # Exact match on any key
        for person in self.people:
            if mention_lower in person._match_keys:
                return person

        # Substring match (e.g., "ondrej" in "ondrej chvala")
        for person in self.people:
            for key in person._match_keys:
                if mention_lower in key or key in mention_lower:
                    return person

        return None

    def match_initiative(self, mention: str) -> Optional[Initiative]:
        """Fuzzy-match a topic mention to a known initiative.

        Handles phrases like "bubble flow" → "Bubble Flow Loop DT",
        "PXI" → "NETL PXI", repo paths, etc.
        """
        mention_lower = mention.lower().strip()
        if not mention_lower:
            return None

        # Exact name match
        for init in self.initiatives:
            if mention_lower == init.name.lower():
                return init

        # Check if mention is contained in initiative name
        for init in self.initiatives:
            if mention_lower in init.name.lower():
                return init

        # Check if mention matches any initiative keyword
        # Only check mention_lower in key (not the reverse) to avoid
        # generic words like "project" false-matching long mentions
        for init in self.initiatives:
            for key in init._match_keys:
                if mention_lower in key:
                    return init

        return None

    def resolve_people(self, names: list[str]) -> list[str]:
        """Resolve a list of name mentions to canonical names."""
        resolved = []
        for name in names:
            person = self.match_person(name)
            if person:
                resolved.append(person.name)
            else:
                resolved.append(name)
        return resolved

    def resolve_initiatives(self, topics: list[str]) -> list[str]:
        """Resolve a list of topic mentions to canonical initiative names."""
        resolved = []
        for topic in topics:
            init = self.match_initiative(topic)
            if init:
                resolved.append(init.name)
            else:
                resolved.append(topic)
        return resolved
