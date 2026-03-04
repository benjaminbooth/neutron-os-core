"""Multi-source repo sensing — provider-based repository activity export.

Providers are auto-imported so they register themselves when the package
is imported.
"""

# Import providers for self-registration
import tools.repo_sensing.providers  # noqa: F401
