"""neut rag — thin extension wrapper delegating to neutron_os.rag.cli."""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> None:
    from neutron_os.rag.cli import main as rag_main

    rag_main(argv)


if __name__ == "__main__":
    main(sys.argv[1:])
