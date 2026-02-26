# DocFlow Setup & Onboarding Guide

## 🚀 Quick Start (5 minutes)

### Option A: One-Step Bootstrap (Recommended)

The easiest way to get started is with the bootstrap script, which handles all dependencies and infrastructure:

```bash
cd /Users/ben/Projects/UT_Computational_NE/Neutron_OS/docs/_tools/docflow
./bootstrap.sh
```

This will:
- ✅ Check for and install missing dependencies (Docker, kubectl, k3d, helm)
- ✅ Create a local K3D cluster with container registry
- ✅ Deploy PostgreSQL with pgvector extension
- ✅ Deploy Redis for caching
- ✅ Deploy Ollama for local LLM
- ✅ Verify all services are healthy

**Options:**
- `--dry-run` — Preview what will be done without making changes
- `--yes` — Auto-accept all prompts (CI/CD mode)
- `--no-install` — Don't offer to install missing dependencies
- `--verbose` — Show detailed output

**Then install the Python package:**
```bash
pip install -e ".[onedrive,diagrams,embedding,llm,langgraph]"
```

---

### Option B: Manual Setup

#### Step 1: Install DocFlow

```bash
# Clone the repository (if not already done)
cd /Users/ben/Projects/UT_Computational_NE/Neutron_OS/docs/_tools
git clone [your-docflow-repo] docflow

# Install with all features
cd docflow
pip install -e ".[onedrive,diagrams,embedding,llm,langgraph]"

# Or install minimal version
pip install -e .
```

#### Step 2: Install System Dependencies

```bash
# macOS
brew install graphviz plantuml

# Linux
apt-get install graphviz plantuml

# Optional: Vega for data visualizations
npm install -g vega-cli
```

### Step 3: Initialize Configuration

```bash
# Create config from template
cp .doc-workflow.yaml.template .doc-workflow.yaml

# Or use the setup wizard
docflow init
```

### Step 4: Configure Providers

Edit `.doc-workflow.yaml`:

```yaml
# Minimal configuration for getting started
repository_root: /Users/ben/Projects/UT_Computational_NE

# Storage provider (start with local for testing)
storage_provider: local
local_storage_path: ./docflow_storage

# LLM provider (Anthropic Claude)
llm_provider: anthropic
anthropic_api_key: ${ANTHROPIC_API_KEY}  # Set as environment variable

# Notification (optional initially)
notification_provider: email
smtp_server: smtp.gmail.com
smtp_port: 587
```

### Step 5: Set Environment Variables

```bash
# Add to ~/.zshrc or ~/.bash_profile
export ANTHROPIC_API_KEY="your-api-key-here"
export DOCFLOW_CONFIG="/Users/ben/Projects/UT_Computational_NE/Neutron_OS/docs/_tools/docflow/.doc-workflow.yaml"

# Reload shell
source ~/.zshrc
```

### Step 6: Test Installation

```bash
# Check CLI is working
docflow --help

# Test diagram generation
docflow diagram generate examples/diagram_example.md

# Check status
docflow status
```

---

## 📚 Complete Setup Guide

### A. Microsoft 365 Integration (OneDrive)

#### 1. Register Azure AD Application

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to "Azure Active Directory" → "App registrations"
3. Click "New registration"
   - Name: `DocFlow UT`
   - Supported account types: "Single tenant"
   - Redirect URI: `http://localhost:8080/callback`
4. Note the **Application (client) ID**

#### 2. Create Client Secret

1. In your app registration, go to "Certificates & secrets"
2. Click "New client secret"
3. Description: `DocFlow CLI`
4. Expires: 24 months
5. Copy the **Value** (you won't see it again!)

#### 3. Configure API Permissions

1. Go to "API permissions"
2. Click "Add a permission"
3. Choose "Microsoft Graph"
4. Add these delegated permissions:
   - `Files.ReadWrite.All`
   - `Sites.ReadWrite.All`
   - `User.Read`
5. Click "Grant admin consent" (may need IT admin)

#### 4. Update Configuration

```yaml
storage_provider: onedrive
onedrive:
  tenant_id: "your-tenant-id"
  client_id: "your-client-id"
  client_secret: ${ONEDRIVE_CLIENT_SECRET}
  site_id: "your-sharepoint-site-id"  # Optional
  drive_id: "your-drive-id"           # Optional
```

### B. Google Workspace Integration (Google Drive)

#### 1. Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create new project or select existing
3. Enable APIs:
   - Google Drive API
   - Google Docs API
   - Google Sheets API (for reports)
4. Note your **Project ID**

#### 2. Create Service Account

1. Navigate to "IAM & Admin" → "Service Accounts"
2. Click "Create Service Account"
   - Name: `docflow-service`
   - Role: "Editor"
3. Create and download JSON key
4. Save as `google-credentials.json`

#### 3. OAuth 2.0 for User Access (Alternative)

1. Go to "APIs & Services" → "Credentials"
2. Create OAuth 2.0 Client ID
   - Application type: "Desktop app"
   - Name: `DocFlow Desktop`
3. Download client configuration
4. Save as `client_secrets.json`

#### 4. Configure Google Drive Settings

```yaml
storage_provider: google_drive
google_drive:
  credentials_path: ${GOOGLE_APPLICATION_CREDENTIALS}
  folder_id: "your-shared-folder-id"  # Optional: specific folder
  service_account_email: "docflow@project.iam.gserviceaccount.com"
  # OR for OAuth:
  oauth_credentials: "client_secrets.json"
  oauth_token_file: ".google_token.json"
```

#### 5. Share Drive Folder with Service Account

```bash
# If using service account, share the target folder with:
# docflow@project.iam.gserviceaccount.com
# Give "Editor" permissions
```

### C. Multi-Cloud Storage Support

```yaml
# Configure multiple storage providers
storage_providers:
  primary: onedrive
  secondary: google_drive
  sync_enabled: true
  conflict_resolution: "newest"  # or "primary", "manual"

# Provider-specific settings
onedrive:
  # ... (as above)

google_drive:
  # ... (as above)

# Dropbox support (future)
dropbox:
  app_key: ${DROPBOX_APP_KEY}
  app_secret: ${DROPBOX_APP_SECRET}
  access_token: ${DROPBOX_ACCESS_TOKEN}

# Box support (future)
box:
  client_id: ${BOX_CLIENT_ID}
  client_secret: ${BOX_CLIENT_SECRET}
  enterprise_id: ${BOX_ENTERPRISE_ID}
```

### D. Vector Database Setup (for RAG)

#### Option 1: ChromaDB (Default, Local)

```bash
# Already installed with pip install docflow[embedding]
# No additional setup needed
```

#### Option 2: Pinecone (Cloud)

```bash
# Sign up at https://www.pinecone.io
# Create index: "docflow-docs"

# Add to config
embedding_provider: pinecone
pinecone:
  api_key: ${PINECONE_API_KEY}
  environment: "us-east-1"
  index_name: "docflow-docs"
```

#### Option 3: pgvector (PostgreSQL)

```bash
# Install PostgreSQL with pgvector extension
brew install postgresql
brew install pgvector

# Create database
createdb docflow

# Enable extension
psql docflow -c "CREATE EXTENSION vector;"

# Add to config
embedding_provider: pgvector
pgvector:
  connection_string: "postgresql://localhost/docflow"
```

### E. Email/Teams Notifications

#### Email (SMTP)

```yaml
notification_provider: email
email:
  smtp_server: smtp.gmail.com
  smtp_port: 587
  sender: "docflow@yourorg.com"
  password: ${EMAIL_PASSWORD}
  use_tls: true
```

#### Microsoft Teams

```yaml
notification_provider: teams
teams:
  webhook_url: "https://outlook.office.com/webhook/..."
  channel: "Documentation"
```

---

## 🔄 Onboarding Existing Documents

### Supported Document Formats

DocFlow supports multiple document formats for both import and export:

#### Source Formats (Import From)
- **Markdown** (.md, .markdown) - Primary format
- **Word Documents** (.docx, .doc)
- **Google Docs** (via API)
- **HTML** (.html, .htm)
- **reStructuredText** (.rst) - Sphinx docs
- **AsciiDoc** (.adoc, .asciidoc)
- **LaTeX** (.tex) - Academic papers
- **Jupyter Notebooks** (.ipynb)
- **XML** (.xml, .dita) - Technical docs
- **JSON** (.json) - Structured data
- **YAML** (.yaml, .yml) - Configuration docs
- **Plain Text** (.txt)
- **Org Mode** (.org) - Emacs format
- **MediaWiki** (.wiki)
- **Confluence** (via API)

#### Target Formats (Export To)
- **Word** (.docx) via OneDrive
- **Google Docs** via Google Drive
- **PDF** (via Pandoc)
- **HTML** (static sites)
- **Confluence** pages
- **SharePoint** pages
- **GitHub/GitLab** wikis
- **Static Sites** (Hugo, Jekyll, MkDocs)

### Format Conversion Examples

```bash
# Convert from various sources
docflow convert --from rst --to md docs/**/*.rst
docflow convert --from latex --to docx paper.tex
docflow convert --from jupyter --to md notebooks/*.ipynb
docflow convert --from xml --to md --xml-schema dita specs/*.xml
docflow convert --from json --to md --json-template api-doc data/*.json

# Bulk conversion with mapping
docflow convert bulk \
  --mapping "*.rst:md,*.tex:docx,*.ipynb:md" \
  --output-dir converted/

# Smart format detection
docflow convert auto /path/to/mixed/docs
```

### Automatic Discovery & Linking

DocFlow can automatically discover and link your existing documents across all supported formats:

### Step 1: Run Discovery

```bash
# Point to your documentation root (auto-detects formats)
docflow onboard discover /Users/ben/Projects/UT_Computational_NE \
  --recursive \
  --include "*.md,*.rst,*.tex,*.xml,*.json,*.ipynb,*.adoc" \
  --exclude "node_modules,build,.git"

# Or use format groups
docflow onboard discover /Users/ben/Projects/UT_Computational_NE \
  --formats "markdown,restructured,latex,jupyter" \
  --recursive
```

This will:
1. Find all markdown files
2. Parse internal links
3. Build a dependency graph
4. Identify the most connected documents

### Step 2: Analyze Link Graph

```bash
# Find the document with the most internal links (likely your index/readme)
docflow onboard analyze-links

# Output:
# Document Link Analysis
# ======================
# 1. README.md (87 outgoing links, 12 incoming)
# 2. docs/architecture.md (45 outgoing, 23 incoming)
# 3. docs/api/index.md (38 outgoing, 15 incoming)
# ...
```

### Step 3: Interactive Onboarding

```bash
# Start from the most connected document
docflow onboard start --root README.md
```

This launches an interactive session:

```
DocFlow Onboarding Assistant
============================

Found 156 markdown documents in repository.
Starting from: README.md (87 internal links)

Processing linked documents...

1. README.md → docs/getting-started.md
   Status: ✅ File exists locally
   OneDrive: ❌ Not found
   
   Action? [l]ink existing, [p]ublish new, [s]kip, [i]gnore permanently
   > p
   
   ✓ Marked for publishing as new draft

2. README.md → docs/architecture.md
   Status: ✅ File exists locally
   OneDrive: 🔍 Found: "Architecture Design.docx" (90% similarity)
   Last modified: 2 days ago by Sarah Chen
   
   Action? [l]ink existing, [p]ublish new, [s]kip, [r]eplace, [m]erge
   > l
   
   ✓ Linked to existing OneDrive document

3. README.md → api/reference.md
   Status: ⚠️ File missing locally
   OneDrive: 🔍 Found: "API Reference.docx"
   
   Action? [d]ownload and create, [i]gnore, [c]reate placeholder
   > d
   
   ✓ Downloaded and created api/reference.md

[Continue through all linked documents...]

Summary:
- 45 documents linked to existing OneDrive files
- 28 documents to be published as new
- 12 documents downloaded from OneDrive
- 3 documents skipped
- 8 broken links identified

Proceed with onboarding? [Y/n] y
```

### Step 4: Bulk Import Options

For large repositories, use bulk operations:

```bash
# Option A: Link all with exact name matches
docflow onboard bulk-link --strategy exact-match

# Option B: Link using fuzzy matching (>80% similarity)
docflow onboard bulk-link --strategy fuzzy --threshold 0.8

# Option C: Publish all as new (fresh start)
docflow onboard bulk-publish --draft

# Option D: Smart mode - AI decides for each document
docflow onboard bulk-smart
```

### Step 5: Verify Onboarding

```bash
# Check link integrity
docflow check-links --verbose

# Show onboarding report
docflow onboard report

# Output:
Onboarding Report
=================
Repository: /Users/ben/Projects/UT_Computational_NE
Total Documents: 156
Status:
  ✅ Linked: 89 (57%)
  📝 Draft: 45 (29%)
  ⏳ Pending: 12 (8%)
  ❌ Failed: 10 (6%)

Link Health:
  ✅ Valid internal links: 423/450 (94%)
  ⚠️ Broken links: 27
  🔄 Redirect needed: 15

Next Steps:
1. Fix broken links: docflow fix-links --auto
2. Publish drafts: docflow publish --all-drafts
3. Set up review cycles: docflow review setup
```

---

## 🎯 Onboarding Decision Matrix

When DocFlow finds existing documents, it uses this decision matrix:

| Local File | OneDrive File | Similarity | Recommended Action | Rationale |
|------------|---------------|------------|-------------------|-----------|
| ✅ Exists | ❌ Not found | - | **Publish New** | Create fresh in OneDrive |
| ✅ Exists | ✅ Found | >90% | **Link** | Nearly identical, safe to link |
| ✅ Exists | ✅ Found | 70-90% | **Review & Link** | Similar but check changes |
| ✅ Exists | ✅ Found | <70% | **Publish New** | Too different, avoid confusion |
| ❌ Missing | ✅ Found | - | **Download** | Recover missing local file |
| ✅ Exists | 🔄 Multiple | - | **Choose** | Manual selection needed |
| 🔄 Non-MD | ✅ Found | - | **Convert & Link** | Convert format then link |
| 📄 XML/JSON | ❌ Not found | - | **Transform & Publish** | Convert structured data |

### Smart Matching Criteria

DocFlow uses multiple signals to match documents:

1. **Filename similarity** (exact, stem, fuzzy)
2. **Title extraction** (from frontmatter or first heading)
3. **Content fingerprint** (first paragraph hash)
4. **Link relationships** (documents that link to each other)
5. **Metadata** (author, date, tags if available)

---

## 🔧 Configuration Deep Dive

### Full Configuration Template

```yaml
# Repository settings
repository_root: /Users/ben/Projects/UT_Computational_NE
state_db_path: ./.docflow/state.db
workflow_checkpoint_path: ./.docflow/checkpoints.db

# Document processing
markdown_extensions: [md, markdown]
supported_formats: [md, rst, tex, xml, json, yaml, ipynb, adoc, html, docx]
ignore_patterns: ["**/node_modules/**", "**/.git/**", "**/build/**"]
  
# Storage provider
storage_provider: onedrive  # local, onedrive, google_drive, multi
onedrive:
  tenant_id: ${AZURE_TENANT_ID}
  client_id: ${AZURE_CLIENT_ID}
  client_secret: ${AZURE_CLIENT_SECRET}
  site_id: optional-sharepoint-site
  drive_id: optional-specific-drive

# LLM provider  
llm_provider: anthropic  # anthropic, openai, azure-openai
anthropic:
  api_key: ${ANTHROPIC_API_KEY}
  model: claude-3-haiku-20240307
  max_tokens: 4000
  temperature: 0.3

# Embedding provider
embedding_provider: chroma  # chroma, pinecone, pgvector
chroma:
  persist_directory: ./.docflow/chroma
  collection_name: docflow_docs

# Notification provider
notification_provider: multi  # email, teams, slack, multi
multi:
  providers: [email, teams]
  email:
    smtp_server: smtp.gmail.com
    smtp_port: 587
  teams:
    webhook_url: ${TEAMS_WEBHOOK}

# Review settings
review:
  default_duration_days: 7
  auto_extend_days: 3
  require_all_reviewers: false
  promotion_threshold: 1  # Number of approvals needed

# Autonomy settings
autonomy:
  level: assisted  # manual, assisted, review, notify, autonomous
  allowed_actions:
    - categorize_comments
    - suggest_changes
    - update_drafts
  blocked_actions:
    - publish_to_production
    - delete_documents

# Git integration
git:
  branch_policies:
    main: canonical
    release/*: canonical
    feature/*: draft
    personal/*: ignore
  auto_commit: true
  commit_message_template: "DocFlow: {action} for {document}"

# Diagram settings
diagrams:
  output_directory: ./.diagrams
  quality_threshold: 8.0
  max_iterations: 3
  design_system_path: ./design-system.yaml

# Meeting intelligence
meetings:
  transcript_directory: ./meeting_transcripts
  auto_process: true
  extract_decisions: true
  extract_actions: true
  link_to_documents: true

# Daemon settings
daemon:
  enabled: false
  interval_minutes: 30
  working_hours: "9:00-17:00"
  timezone: "America/Chicago"
```

### Environment Variables

Create `.env` file:

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...
DOCFLOW_CONFIG=/path/to/.doc-workflow.yaml

# OneDrive (if using)
AZURE_TENANT_ID=...
AZURE_CLIENT_ID=...
AZURE_CLIENT_SECRET=...

# Optional
TEAMS_WEBHOOK=https://...
EMAIL_PASSWORD=...
PINECONE_API_KEY=...
OPENAI_API_KEY=...
```

---

## 🎨 Design System Customization

### Generate Template

```bash
docflow diagram design-system --output-path design-system.yaml
```

### Customize Colors and Fonts

```yaml
colors:
  primary: "#FF6B35"      # UT Orange
  secondary: "#004E7C"    # UT Navy
  accent: "#5C946E"       # Success green
  danger: "#DC2626"       # Error red
  neutral_light: "#F7F7F7"
  neutral_dark: "#1A1A1A"

typography:
  fonts_approved:
    - family: "Inter"
      weights: ["400", "600", "700"]
    - family: "JetBrains Mono"
      weights: ["400"]
  sizes:
    title: 20
    label: 13
    annotation: 11

spacing:
  horizontal_padding: 24
  vertical_padding: 18
  element_spacing: 36
```

---

## 🚦 Verification Steps

### 1. Test Diagram Generation

```bash
# Generate example diagrams
docflow diagram generate examples/diagram_example.md

# Check quality
docflow diagram evaluate examples/diagrams/diagram_01.svg
```

### 2. Test Document Publishing

```bash
# Publish a test document
echo "# Test Document\nThis is a test." > test.md
docflow publish test.md --draft

# Check status
docflow status
```

### 3. Test OneDrive Connection

```bash
# List OneDrive documents
docflow storage list

# Test upload
docflow storage upload test.md
```

### 4. Test LLM Integration

```bash
# Test comment categorization
docflow test llm --prompt "This section needs clarification"

# Expected output:
# Category: clarification
# Confidence: 0.92
```

---

## 📊 Dashboard & Monitoring

### Start Web Dashboard (Coming Soon)

```bash
docflow dashboard --port 8080

# Open http://localhost:8080
```

### CLI Monitoring

```bash
# Overall status
docflow status

# Watch mode (auto-refresh)
docflow status --watch

# Detailed metrics
docflow metrics

# Recent activity
docflow activity --last 24h
```

---

## 🔥 Common Issues & Solutions

### Issue: "Graphviz not found"

```bash
# macOS
brew install graphviz

# Linux
apt-get install graphviz

# Verify
which dot
```

### Issue: "API Key not found"

```bash
# Check environment
echo $ANTHROPIC_API_KEY

# Set it
export ANTHROPIC_API_KEY="sk-ant-..."

# Or add to .env
echo "ANTHROPIC_API_KEY=sk-ant-..." >> .env
```

### Issue: "OneDrive authentication failed"

1. Check app registration in Azure
2. Verify permissions are granted
3. Regenerate client secret if expired
4. Test with: `docflow storage test`

### Issue: "Broken links after import"

```bash
# Auto-fix common patterns
docflow fix-links --auto

# Manual review
docflow check-links --interactive
```

---

## 🎯 Next Steps After Setup

1. **Set up review cycles**
   ```bash
   docflow review setup --weekly
   ```

2. **Enable daemon for automation**
   ```bash
   docflow daemon start
   ```

3. **Configure team notifications**
   ```bash
   docflow notify configure
   ```

4. **Create first workflow**
   ```bash
   docflow workflow create standard-review
   ```

5. **Train team**
   ```bash
   docflow tutorial
   ```

---

## 📞 Support

- **Documentation**: `/docs/_tools/docflow/README.md`
- **Examples**: `/docs/_tools/docflow/examples/`
- **Logs**: `./.docflow/logs/`
- **Debug mode**: `docflow --debug [command]`

---

## ✅ Setup Checklist

- [ ] DocFlow installed with pip
- [ ] System dependencies installed (graphviz, etc.)
- [ ] Configuration file created
- [ ] Environment variables set
- [ ] API keys configured
- [ ] Test document published successfully
- [ ] Diagram generation working
- [ ] OneDrive connection verified (if using)
- [ ] Existing documents discovered
- [ ] Onboarding decisions made
- [ ] Links verified and fixed
- [ ] Team notified of new system
- [ ] First review cycle created
- [ ] Daemon running (optional)
- [ ] Backups configured

---

**Setup typically takes 15-30 minutes. Onboarding depends on repository size (usually 1-2 hours for ~100 documents).**