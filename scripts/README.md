# `scripts/` — Global Bootstrap and Installation Scripts

Shell scripts and system configs that operate at the repo or system level.

## Contents

- `bootstrap.sh` — One-command dev environment setup
- `com.utcomputational.gitlab-export.plist` — macOS launchd config for exports

## What belongs here

- Environment bootstrap and installation scripts
- System-level configs (launchd, systemd, cron)
- CI/CD helper scripts that aren't part of `.gitlab-ci.yml`

## What does NOT belong here

- **Extension-specific scripts** → `src/neutron_os/extensions/builtins/{ext}/infra/`
- **Python code** → `src/neutron_os/`
- **Terraform/Helm** → `infra/`

## AI Agent Policy

Scripts here should be idempotent and safe to re-run. Do not add Python
entry points here — use the extension CLI system instead. Extension-specific
deployment configs belong in their extension's `infra/` subdirectory.
