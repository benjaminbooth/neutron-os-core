#!/usr/bin/env bash
# Rename all docs to consistent convention:
# - Hyphens everywhere (no underscores in filenames)
# - Type prefix: prd-, spec-, adr-
# - Drop redundant "neutron-os-" from spec filenames
# - docs/specs/ → docs/tech-specs/
#
# This script:
# 1. Renames the directory
# 2. Renames all files via git mv
# 3. Updates all cross-references in all .md files
# 4. Updates CLAUDE.md, README.md, code references

set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

echo "=== Step 1: Rename docs/specs/ → docs/tech-specs/ ==="
git mv docs/specs docs/tech-specs
echo "  Done"

echo ""
echo "=== Step 2: Rename spec files ==="

# Specs: drop "neutron-os-", add "spec-" prefix where missing, normalize
declare -A SPEC_MAP=(
  ["spec-agent-state-management.md"]="spec-agent-state-management.md"
  ["spec-brand-identity.md"]="spec-spec-brand-identity.md"
  ["spec-console-check-ui-mockups.md"]="spec-spec-console-check-ui-mockups.md"
  ["spec-data-architecture.md"]="spec-data-architecture.md"
  ["spec-design-loop-architecture.md"]="spec-spec-design-loop-architecture.md"
  ["spec-digital-twin-architecture.md"]="spec-digital-twin-architecture.md"
  ["spec-merge-scenario-guide.md"]="spec-spec-merge-scenario-guide.md"
  ["spec-mermaid-best-practices.md"]="spec-mermaid-best-practices.md"
  ["spec-metrics-framework.md"]="spec-spec-metrics-framework.md"
  ["spec-neut-cli.md"]="spec-neut-cli.md"
  ["spec-agent-architecture.md"]="spec-agent-architecture.md"
  ["spec-connections.md"]="spec-connections.md"
  ["spec-executive.md"]="spec-executive.md"
  ["spec-model-routing.md"]="spec-model-routing.md"
  ["spec-publisher.md"]="spec-publisher.md"
  ["spec-rag-architecture.md"]="spec-rag-architecture.md"
  ["spec-nrad-ontology-mapping.md"]="spec-spec-nrad-ontology-mapping.md"
  ["spec-stakeholder-interview-guide.md"]="spec-spec-stakeholder-interview-guide.md"
)

for old in "${!SPEC_MAP[@]}"; do
  new="${SPEC_MAP[$old]}"
  if [ -f "docs/tech-specs/$old" ]; then
    git mv "docs/tech-specs/$old" "docs/tech-specs/$new"
    echo "  $old → $new"
  fi
done

echo ""
echo "=== Step 3: Rename PRD files ==="

declare -A PRD_MAP=(
  ["prd-agent-state-management.md"]="prd-agent-state-management.md"
  ["prd-analytics-dashboards.md"]="prd-analytics-dashboards.md"
  ["prd-compliance-tracking.md"]="prd-compliance-tracking.md"
  ["prd-connections.md"]="prd-connections.md"
  ["prd-data-platform.md"]="prd-data-platform.md"
  ["prd-experiment-manager.md"]="prd-experiment-manager.md"
  ["prd-intelligence-amplification.md"]="prd-intelligence-amplification.md"
  ["prd-media-library.md"]="prd-media-library.md"
  ["prd-medical-isotope.md"]="prd-medical-isotope.md"
  ["prd-neut-cli.md"]="prd-neut-cli.md"
  ["prd-agents.md"]="prd-agents.md"
  ["prd-executive.md"]="prd-executive.md"
  ["prd-okrs-2026.md"]="prd-okrs-2026.md"
  ["prd-publisher.md"]="prd-publisher.md"
  ["prd-reactor-ops-log.md"]="prd-reactor-ops-log.md"
  ["prd-scheduling-system.md"]="prd-scheduling-system.md"
  ["prd-security-access-control.md"]="prd-security-access-control.md"
  ["prd-template-one-page.md"]="prd-template-one-page.md"
)

for old in "${!PRD_MAP[@]}"; do
  new="${PRD_MAP[$old]}"
  if [ -f "docs/requirements/$old" ]; then
    git mv "docs/requirements/$old" "docs/requirements/$new"
    echo "  $old → $new"
  fi
done

echo ""
echo "=== Step 4: Rename ADR files ==="

declare -A ADR_MAP=(
  ["adr_001-polyglot-monorepo-bazel.md"]="adr-001-polyglot-monorepo-bazel.md"
  ["adr_002-hyperledger-fabric-multi-facility.md"]="adr-002-hyperledger-fabric-multi-facility.md"
  ["adr_003-lakehouse-iceberg-duckdb-superset.md"]="adr-003-lakehouse-iceberg-duckdb-superset.md"
  ["adr_004-infrastructure-terraform-k8s-helm.md"]="adr-004-infrastructure-terraform-k8s-helm.md"
  ["adr_005-meeting-intake-pipeline.md"]="adr-005-meeting-intake-pipeline.md"
  ["adr_006-mcp-server-agentic-access.md"]="adr-006-mcp-agentic-access.md"
  ["adr_007-streaming-first-architecture.md"]="adr-007-streaming-first-architecture.md"
  ["adr_008-wasm-extension-runtime.md"]="adr-008-wasm-extension-runtime.md"
  ["adr_009-promote-media-internalize-db.md"]="adr-009-promote-media-internalize-db.md"
  ["adr_010-cli-architecture.md"]="adr-010-cli-architecture.md"
)

for old in "${!ADR_MAP[@]}"; do
  new="${ADR_MAP[$old]}"
  if [ -f "docs/requirements/$old" ]; then
    git mv "docs/requirements/$old" "docs/requirements/$new"
    echo "  $old → $new"
  fi
done

echo ""
echo "=== Step 5: Update cross-references ==="

# Build sed commands for all renames
# Order matters: longer patterns first to avoid partial matches

# Directory rename: docs/specs/ → docs/tech-specs/
find . -name "*.md" -not -path "./.git/*" -not -path "./.venv/*" -not -path "./node_modules/*" | while read f; do
  sed -i '' 's|docs/specs/|docs/tech-specs/|g; s|\.\./specs/|../tech-specs/|g' "$f"
done
echo "  Updated docs/specs/ → docs/tech-specs/"

# Spec file renames (in cross-references)
for old in "${!SPEC_MAP[@]}"; do
  new="${SPEC_MAP[$old]}"
  find . -name "*.md" -not -path "./.git/*" -not -path "./.venv/*" | while read f; do
    sed -i '' "s|${old}|${new}|g" "$f"
  done
done
echo "  Updated spec cross-references"

# PRD file renames
for old in "${!PRD_MAP[@]}"; do
  new="${PRD_MAP[$old]}"
  find . -name "*.md" -not -path "./.git/*" -not -path "./.venv/*" | while read f; do
    sed -i '' "s|${old}|${new}|g" "$f"
  done
done
echo "  Updated PRD cross-references"

# ADR file renames
for old in "${!ADR_MAP[@]}"; do
  new="${ADR_MAP[$old]}"
  find . -name "*.md" -not -path "./.git/*" -not -path "./.venv/*" | while read f; do
    sed -i '' "s|${old}|${new}|g" "$f"
  done
done
echo "  Updated ADR cross-references"

echo ""
echo "=== Step 6: Update code references ==="

# Update Python/TOML/YAML/shell files
for old in "${!SPEC_MAP[@]}"; do
  new="${SPEC_MAP[$old]}"
  find src/ tests/ scripts/ -type f \( -name "*.py" -o -name "*.toml" -o -name "*.yaml" -o -name "*.sh" \) -not -path "*__pycache__*" 2>/dev/null | while read f; do
    sed -i '' "s|${old}|${new}|g" "$f" 2>/dev/null || true
  done
done

for old in "${!PRD_MAP[@]}"; do
  new="${PRD_MAP[$old]}"
  find src/ tests/ scripts/ -type f \( -name "*.py" -o -name "*.toml" -o -name "*.yaml" -o -name "*.sh" \) -not -path "*__pycache__*" 2>/dev/null | while read f; do
    sed -i '' "s|${old}|${new}|g" "$f" 2>/dev/null || true
  done
done

# Fix directory references in Python files
find src/ tests/ -name "*.py" -not -path "*__pycache__*" | while read f; do
  sed -i '' 's|docs/specs/|docs/tech-specs/|g' "$f" 2>/dev/null || true
done

echo "  Updated code references"

# Also update .publisher.yaml
if [ -f .publisher.yaml ]; then
  sed -i '' 's|docs/specs|docs/tech-specs|g; s|prd_|prd-|g' .publisher.yaml
  echo "  Updated .publisher.yaml"
fi

# Update .publisher.json manifests
find . -name ".publisher.json" -not -path "./.git/*" | while read f; do
  sed -i '' 's|prd_|prd-|g' "$f" 2>/dev/null || true
done

echo ""
echo "=== Step 7: Clean stale .neut/docflow ==="
git rm -r --cached .neut/docflow/ 2>/dev/null || true
echo "  Cleaned .neut/docflow"

echo ""
echo "=== Done ==="
echo "Run: git diff --stat to review, then git add -A && git commit"
