# Contributing to Neutron OS

## Development Setup

```bash
git clone https://rsicc-gitlab.tacc.utexas.edu/neutron-os/neutron-os-core.git
cd neutron_os
# Your IDE will auto-detect .gitignore patterns
```

## Git Workflow

### Committing Code
1. Create a feature branch: `git checkout -b feature/description`
2. Make changes and commit with clear messages
3. Push and open a merge request

### What Gets Ignored

Our `.gitignore` automatically excludes:
- **Python artifacts**: `__pycache__`, `.venv`, `.pytest_cache`, `*.egg-info`
- **Environment files**: `.env`, `.env.local` (never commit secrets!)
- **Build outputs**: `build/`, `dist/`, `*.so`
- **IDE files**: `.vscode/`, `.idea/`, `*.swp`
- **Data/Logs**: `*.csv`, `*.h5`, `*.log`, `logs/`
- **Generated docs**: `docs/_tools/generated/`, `docs/_tools/test/`

**No action needed** — these patterns apply automatically when you clone the repo.

### Maintaining .gitignore

When adding a new tool, language, or dependency type:

1. **Check for existing patterns** in `.gitignore` first
2. **Add patterns following existing style** (grouped by category with comments)
3. **Test locally**: 
   ```bash
   git check-ignore -v your_file_pattern
   ```
4. **Commit as separate change**:
   ```bash
   git add .gitignore
   git commit -m "Update .gitignore: add [tool/language] patterns"
   ```
5. **Open merge request** for visibility to team

### Pattern Examples

```bash
# OS artifacts
.DS_Store
.AppleDouble

# Python: bytecode and packages
__pycache__/
*.py[cod]
*.egg-info/

# Data: don't commit large files
*.parquet
*.h5

# Environment: NEVER commit secrets
.env
.env.local
```

**Golden Rule:** If it's a file you don't want 100 copies of in git history, add it to `.gitignore`.

## Standards & References

See [CLAUDE.md](CLAUDE.md) for documentation and terminology conventions.

Standard practices follow GitHub's [Python .gitignore template](https://github.com/github/gitignore/blob/main/Python.gitignore).
