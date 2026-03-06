"""NeutronOS test orchestration.

Coordinates multiple test types:
- Unit tests
- Integration tests
- Database migration tests
- Linting (ruff)
- Type checking (optional)

Use via CLI:
    neut test              # Default: quick local tests
    neut test --full       # Comprehensive tests
    neut test --pr         # Tests required for PR approval
    neut test --release    # Full release candidate validation
"""
