"""NeutronOS database infrastructure management.

This module provides shared PostgreSQL + pgvector infrastructure used
across all NeutronOS components (Sense, Chat, etc.).

Commands:
    neut db up        Start local K3D cluster with PostgreSQL
    neut db down      Stop local cluster
    neut db delete    Delete cluster and all data
    neut db status    Show cluster and database status
    neut db migrate   Run schema migrations
    neut db bootstrap Full setup from scratch
"""
