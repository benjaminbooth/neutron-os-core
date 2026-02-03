# OneDrive Publication Checklist

You have `publish_to_onedrive.py` ready to use! Follow this checklist to publish your 3 required PRDs.

## ✅ Step 1: Get Azure AD Credentials (5 minutes)

- [ ] Go to https://portal.azure.com and sign in with your UT Austin account
- [ ] Search for "App registrations" → click "+ New registration"
- [ ] Name it `Neutron OS Publisher` → click Register
- [ ] **Copy** "Application (client) ID" and save it as `CLIENT_ID`
- [ ] Go to **Certificates & secrets** → "+ New client secret"
- [ ] Set to 24 months → copy the **Value** → save as `CLIENT_SECRET`
- [ ] Go back to **Overview** → copy "Directory (tenant) ID" → save as `TENANT_ID`
- [ ] Go to **API permissions** → "+ Add a permission"
  - [ ] Select **Microsoft Graph**
  - [ ] **Application permissions**
  - [ ] Search & select: `Files.ReadWrite.All` + `Sites.ReadWrite.All`
  - [ ] Click "Grant admin consent for UT Austin"

## ✅ Step 2: Get Your OneDrive Folder ID (2 minutes)

**Option A (Easiest):** Use OneDrive root
- [ ] Leave `ONEDRIVE_FOLDER_ID` unset in script

**Option B:** Use specific folder
- [ ] Go to https://utexas-my.sharepoint.com
- [ ] Navigate to your target folder
- [ ] Right-click → Copy link
- [ ] Extract folder ID from URL
- [ ] Save as `ONEDRIVE_FOLDER_ID`

## ✅ Step 3: Set Credentials (2 minutes)

**Option A: Environment Variables (Recommended)**

```bash
export MS_GRAPH_CLIENT_ID="your-app-id-from-step-1"
export MS_GRAPH_CLIENT_SECRET="your-secret-from-step-1"
export MS_GRAPH_TENANT_ID="your-tenant-id-from-step-1"
export ONEDRIVE_FOLDER_ID="your-folder-id-from-step-2"  # or skip this line
```

**Option B: Edit Script**

Edit `docs/_tools/publish_to_onedrive.py` line ~49-52:

```python
class Config:
    TENANT_ID = "your-tenant-id"
    CLIENT_ID = "your-app-id"
    CLIENT_SECRET = "your-secret"
    ONEDRIVE_FOLDER_ID = "your-folder-id"  # or leave as "root"
```

## ✅ Step 4: Run Publisher (1 minute)

```bash
cd /Users/ben/Projects/UT_Computational_NE/Neutron_OS

# Method A: With environment variables
python3 docs/_tools/publish_to_onedrive.py --prd

# Method B: If credentials are in script
python3 docs/_tools/publish_to_onedrive.py --prd
```

## ✅ Expected Output

```
======================================================================
🚀 NEUTRON OS DOCUMENT PUBLISHER
======================================================================

📤 Uploading Experiment Manager PRD.docx...
  ✅ Uploaded (ID: 01AB2CD...)
  🔗 Creating shareable link...
  ✅ Link created: https://utexas-my.sharepoint.com/...
  🔐 Setting permissions for utexas.edu...
  ✅ Permissions set
✅ Published: Experiment Manager PRD.docx

[... similar for Data Platform PRD and Reactor Ops Log PRD ...]

======================================================================
📊 PUBLICATION SUMMARY
======================================================================
✅ Experiment Manager PRD.docx
   https://utexas-my.sharepoint.com/personal/bdb3732_eid_utexas_edu/Documents/Experiment%20Manager%20PRD.docx?web=1
✅ Data Platform PRD.docx
   https://utexas-my.sharepoint.com/personal/bdb3732_eid_utexas_edu/Documents/Data%20Platform%20PRD.docx?web=1
✅ Reactor Ops Log PRD.docx
   https://utexas-my.sharepoint.com/personal/bdb3732_eid_utexas_edu/Documents/Reactor%20Ops%20Log%20PRD.docx?web=1

📋 Link manifest saved to docs/_tools/onedrive_manifest.json
```

## ✅ Step 5: Verify & Share

- [ ] Check `docs/_tools/onedrive_manifest.json` for the URLs
- [ ] Click each URL and verify the document opened
- [ ] Verify you can share the link with other UT Austin users
- [ ] Add the links to your README or send to stakeholders

## 📋 What Gets Published

**3 Required PRDs:**
1. Experiment Manager PRD
2. Data Platform PRD  
3. Reactor Ops Log PRD

**5 Supporting PRDs (optional):**
- Neutron OS Executive PRD (already in SharePoint)
- Scheduling System PRD
- Compliance Tracking PRD
- Analytics Dashboards PRD
- Medical Isotope Production PRD

To publish supporting docs:
```bash
# Publish all 8 PRDs
python3 docs/_tools/publish_to_onedrive.py --prd
```

To also publish specifications:
```bash
python3 docs/_tools/publish_to_onedrive.py --prd --specs
```

## 🔗 Cross-Document Links

The script automatically:
- ✅ Generates .docx files from markdown
- ✅ Uploads to your OneDrive
- ✅ Updates internal links to point to OneDrive URLs
- ✅ Sets sharing for UT Austin domain
- ✅ Saves link manifest as JSON

When you open a document, cross-references (e.g., "See [Experiment Manager PRD](...)") will link directly to the OneDrive version.

## ⚠️ Troubleshooting

**"Authentication failed"**
- Check `CLIENT_ID` and `CLIENT_SECRET` are correct
- Verify secret hasn't expired in Azure portal

**"Upload failed: 401"**
- Verify permissions are set: `Files.ReadWrite.All` + `Sites.ReadWrite.All`
- Click "Grant admin consent for UT Austin" in Azure portal

**"File not found"**
- Run from workspace root: `/Users/ben/Projects/UT_Computational_NE/Neutron_OS/`
- Check markdown files exist in `docs/prd/`

**Need help?** See `docs/_tools/PUBLISH_SETUP.md` for detailed guide

---

**Next:** ✅ Complete Step 1 → Run Step 4 → Share the manifest links!
