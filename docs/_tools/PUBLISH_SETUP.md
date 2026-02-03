# OneDrive Publishing Setup Guide

The `publish_to_onedrive.py` utility automates publishing Neutron OS documentation to OneDrive with automatic link fixing and organization sharing.

## Prerequisites

### 1. Python Dependencies

```bash
pip install requests python-docx
```

### 2. Azure AD Application Registration

You need a registered Azure AD app with permissions to upload files to OneDrive.

#### Option A: Manual Setup (via Azure Portal)

1. **Register Application**
   - Go to [Azure Portal](https://portal.azure.com) → Azure AD → App registrations
   - Click "New registration"
   - Name: `Neutron OS Publisher`
   - Supported account types: "Accounts in this organizational directory only"
   - Click Register

2. **Create Client Secret**
   - Go to Certificates & secrets → Client secrets → New client secret
   - Description: `OneDrive publishing`
   - Expiry: 24 months (or longer)
   - Copy the **Value** (you'll need this)

3. **Grant API Permissions**
   - Go to API permissions → Add a permission
   - Microsoft Graph → Application permissions
   - Search for and select:
     - `Files.ReadWrite.All`
     - `Sites.Manage.All` (for sharing)
   - Click "Grant admin consent"

4. **Collect Credentials**
   - Application (client) ID: Copy from Overview page
   - Client secret value: From step 2
   - Tenant ID: From Overview page (or use "common" for multi-tenant)

#### Option B: Using Microsoft Graph PowerShell (Automated)

```powershell
# Install Microsoft.Graph PowerShell module
Install-Module Microsoft.Graph -Scope CurrentUser

# Connect (will prompt for login)
Connect-MgGraph -Scopes "Application.ReadWrite.All", "AppRoleAssignment.ReadWrite.All"

# Create app registration
$app = New-MgApplication -DisplayName "Neutron OS Publisher"

# Create secret
$secret = Add-MgApplicationPassword -ApplicationId $app.Id

# Note the values:
Write-Host "Client ID: $($app.AppId)"
Write-Host "Secret: $($secret.SecretText)"
```

### 3. Configure Environment Variables

**Bash/Zsh:**
```bash
export MS_GRAPH_CLIENT_ID="your-client-id"
export MS_GRAPH_CLIENT_SECRET="your-client-secret"
export MS_GRAPH_TENANT_ID="utexas.onmicrosoft.com"  # or your tenant ID
export ONEDRIVE_FOLDER_ID="root"  # or specific folder ID
```

**Or create `.env` file:**
```
MS_GRAPH_CLIENT_ID=your-client-id
MS_GRAPH_CLIENT_SECRET=your-client-secret
MS_GRAPH_TENANT_ID=utexas.onmicrosoft.com
ONEDRIVE_FOLDER_ID=root
```

Then load it:
```bash
set -a; source .env; set +a
```

### 4. Find Your OneDrive Folder ID (Optional)

If you want to upload to a specific folder instead of root:

```bash
python3 << 'EOF'
from docs._tools.publish_to_onedrive import GraphClient

client = GraphClient()
result = client.get("/me/drive/root/children")

for item in result.get("value", []):
    print(f"{item['name']}: {item['id']}")
EOF
```

Then set `ONEDRIVE_FOLDER_ID` to the folder ID you want.

---

## Usage

### Publish All PRDs
```bash
cd /Users/ben/Projects/UT_Computational_NE/Neutron_OS
python3 docs/_tools/publish_to_onedrive.py --prd
```

### Publish All Specs
```bash
python3 docs/_tools/publish_to_onedrive.py --specs
```

### Publish Everything
```bash
python3 docs/_tools/publish_to_onedrive.py --all
```

---

## What Gets Published

### PRDs (8 documents)
- Experiment Manager PRD
- Data Platform PRD
- Reactor Ops Log PRD
- Neutron OS Executive PRD
- Scheduling System PRD
- Compliance Tracking PRD
- Analytics Dashboards PRD
- Medical Isotope Production PRD

### Specs (3 documents)
- Neutron OS Master Tech Spec
- Data Architecture Spec
- Digital Twin Architecture Spec

---

## Output

After successful publication, a manifest file is created at `docs/_tools/onedrive_manifest.json`:

```json
{
  "published_at": "2026-01-28 15:30:45",
  "documents": {
    "Experiment Manager PRD.docx": "https://utexas-my.sharepoint.com/:w:/r/personal/...",
    "Data Platform PRD.docx": "https://utexas-my.sharepoint.com/:w:/r/personal/...",
    ...
  }
}
```

---

## Troubleshooting

### "Authentication failed"
- Check that `MS_GRAPH_CLIENT_ID` and `MS_GRAPH_CLIENT_SECRET` are set correctly
- Verify the credentials in Azure Portal still match what you set

### "Upload failed"
- Ensure the file exists at the markdown source path
- Check that `ONEDRIVE_FOLDER_ID` is valid (use "root" if unsure)
- Verify your OneDrive has enough storage space

### "Link creation failed"
- Ensure the app has `Files.ReadWrite.All` permission
- Admin consent may be needed—check Azure Portal

### Links not updating
- The utility updates links in hyperlinks; inline text links may not be updated
- Manually verify important links in the generated documents

---

## Security Notes

⚠️ **Never commit credentials to Git:**
```bash
# Prevent accidental commits
echo ".env" >> .gitignore
echo "onedrive_manifest.json" >> .gitignore
```

- Store secrets in environment variables or `.env` (not committed)
- Use a client secret with appropriate expiry (e.g., 12-24 months)
- Rotate secrets periodically
- Consider using Azure Key Vault for production

---

## API References

- [Microsoft Graph Python SDK](https://github.com/microsoftgraph/msgraph-sdk-python)
- [Graph API Drive Items](https://docs.microsoft.com/en-us/graph/api/resources/driveitem)
- [Share File/Folder API](https://docs.microsoft.com/en-us/graph/api/driveitem-createlink)

---

## Future Enhancements

Potential improvements:

1. **Batch processing** - Publish multiple files in parallel
2. **Link fixing** - Parse markdown links and auto-update references between docs
3. **Version tracking** - Maintain version history on OneDrive
4. **Notifications** - Email stakeholders with published link
5. **Permission templates** - Pre-configured sharing rules by document type
6. **Scheduled publishing** - Automated daily/weekly publishes from CI/CD
