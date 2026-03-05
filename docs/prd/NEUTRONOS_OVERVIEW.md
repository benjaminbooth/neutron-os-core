# NeutronOS — Overview

NeutronOS is an umbrella platform and set of integrated services designed to streamline research reactor operations and research workflows for UT's NETL TRIGA and related projects. It is not a single agent or tool; rather, NeutronOS is an ecosystem that includes multiple components and agents that work together to collect, store, analyze, and act on operational data.

Key points:
- NeutronOS = platform + services + data + agents. It includes storage, indexing, RAG services, agent runtime, and governance components.
- Neut Sense = one agent/component inside NeutronOS focused on "sensing" operational signals: ingesting meeting transcripts, voice memos, documents, and other day-to-day artifacts, extracting structured data, and surfacing it for planning, design, and reporting.
- Other components: ingestion pipelines, unified RAG (`signal_rag`), state management, document registries, and specialized modules for simulation, monitoring, and operations.

Why this distinction matters:
- Clarity for IAM & governance: App registrations and permissions should be scoped to the specific component (e.g., Neut Sense) when possible, not to the entire NeutronOS platform.
- Architecture: Development work, deployment boundaries, and security controls differ between platform-level services and single-agent components.
- Communication: When requesting resources, credits, or permissions, name the specific component that needs access (for example, "Neut Sense - Graph API access") and reference NeutronOS as the hosting ecosystem.

How to refer to these in docs and forms:
- Use "NeutronOS" when describing the overall platform, architecture, or multi-component interactions.
- Use "Neut Sense" when describing the sensing/ingestion agent and the specific capabilities it requires (e.g., Graph API scopes, Teams transcript access).

If you want, I can update additional docs to follow this language convention and add a short blurb at top-level READMEs to prevent future conflation.
