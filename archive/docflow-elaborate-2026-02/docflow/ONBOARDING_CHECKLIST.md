# 🚀 DocFlow Personal Onboarding Checklist

## Pre-Flight Check ✅

### 1. Environment Setup

**Option A: One-Step Bootstrap (Recommended)**
- [ ] Run bootstrap script: `./bootstrap.sh`
  - Installs all dependencies (Docker, kubectl, k3d, helm)
  - Creates local K3D cluster with PostgreSQL, Redis, Ollama
  - Use `--dry-run` to preview first
- [ ] Install Python package: `pip install -e ".[dev]"`

**Option B: Manual Setup**
- [ ] Python 3.9+ installed
- [ ] Virtual environment created: `python -m venv .venv`
- [ ] Activated: `source .venv/bin/activate`
- [ ] Dependencies installed: `pip install -r requirements.txt`

### 2. API Keys & Credentials
- [ ] **Anthropic API Key**: Get from https://console.anthropic.com/
  - [ ] Set: `export ANTHROPIC_API_KEY="sk-ant-..."`
  - [ ] Add to `.env` file

- [ ] **OneDrive (if using)**:
  - [ ] Azure App registered
  - [ ] Client ID and Secret obtained
  - [ ] Environment variables set

- [ ] **Google Drive (if using)**:
  - [ ] Google Cloud Project created
  - [ ] Service account OR OAuth configured
  - [ ] Credentials JSON downloaded
  - [ ] Path set in config

### 3. Initial Configuration
```bash
# Initialize DocFlow
docflow init

# This will:
# - Create ~/.docflow/ directory
# - Generate initial config.yaml
# - Set up SQLite database
# - Create folder structure
```

## 🎯 Onboarding Session

### Phase 1: Discovery (5 min)
```bash
# Scan your existing documents
docflow onboard discover

# This will find:
# - Markdown files
# - LaTeX documents
# - XML/JSON configs
# - Jupyter notebooks
# - Any supported format
```

### Phase 2: Import Decision (2 min)
Look at discovered documents and decide:
- [ ] Which documents to import
- [ ] Target state for each (draft/published)
- [ ] Which need conversion
- [ ] Review requirements

### Phase 3: Bulk Import (10 min)
```bash
# Import selected documents
docflow onboard import

# Or selective import:
docflow onboard import --path /specific/folder --state draft
```

### Phase 4: Test Core Features

#### A. Document Creation
```bash
# Create from template
docflow new "API Documentation" --template technical

# From meeting notes
docflow meeting process meeting_notes.md
```

#### B. State Management
```bash
# Move to review
docflow state advance <doc_id> --to review

# Check status
docflow list --state review
```

#### C. Diagram Generation
```bash
# Test AI diagram creation
docflow diagram create "System Architecture" --style flowchart

# Evaluate existing diagram
docflow diagram evaluate architecture.png
```

#### D. Format Conversion
```bash
# Test universal converter
docflow convert input.xml output.md
docflow convert notebook.ipynb documentation.md
```

### Phase 5: Cloud Sync Test

#### OneDrive
```bash
# Test upload
docflow sync push --provider onedrive

# Test comments
docflow review feedback <doc_id>
```

#### Google Drive
```bash
# Test upload
docflow sync push --provider google

# Share document
docflow share <doc_id> colleague@email.com
```

## 📊 Validation Checks

### System Health
```bash
# Check all systems
docflow doctor

# Should show:
# ✅ Database: Connected
# ✅ LLM Provider: Ready
# ✅ Storage: Configured
# ✅ Git: Initialized
```

### Performance Test
```bash
# Process a complex document
docflow workflow run sample_complex.md

# Check metrics
docflow metrics show
```

## 🔄 Feedback Collection Points

After each phase, note:

### Discovery Phase
- [ ] Were all your documents found?
- [ ] Any format not recognized?
- [ ] Discovery speed acceptable?

### Import Phase
- [ ] Conversion quality good?
- [ ] Metadata preserved?
- [ ] Any errors or warnings?

### Feature Testing
- [ ] Which features feel natural?
- [ ] What's missing?
- [ ] Any confusing commands?

### Cloud Integration
- [ ] Auth process smooth?
- [ ] Sync reliable?
- [ ] Comments working?

## 📝 Quick Reference

### Most Used Commands
```bash
# Daily workflow
docflow new "Doc Title"          # Create
docflow edit <id>                # Open in editor
docflow state advance <id>       # Move forward
docflow sync push                # Upload

# Review cycle
docflow review request <id> @reviewer
docflow review feedback <id>
docflow review approve <id>

# Diagrams
docflow diagram create "Title" --style sequence
docflow diagram evaluate diagram.png
```

### Troubleshooting
```bash
# If something breaks
docflow debug --verbose
docflow repair db
docflow cache clear

# Check logs
tail -f ~/.docflow/logs/docflow.log
```

## 🎉 Success Metrics

You're successfully onboarded when:
- [ ] 10+ documents imported
- [ ] Created 1 new document
- [ ] Generated 1 diagram with AI
- [ ] Synced to cloud provider
- [ ] Processed 1 review cycle

## 💭 Notes Section

Use this space to capture your experience:

```
Date: ___________

What worked well:
- 
- 

Pain points:
- 
- 

Feature requests:
- 
- 

Would remove:
- 
- 

Time to productive: _____ minutes
```

---

Ready? Let's go! 🚀

Start with: `docflow init`