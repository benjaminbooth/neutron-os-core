## Integration Request — Neut Sense (NeutronOS component)

Use this file to copy/paste answers into the UT Integration Request form (https://iamservices.utexas.edu/integration-request). Replace ALL-CAPS placeholders before submitting.

---

### 1) Key application info
 - Name: Neut Sense (component of NeutronOS) — integration
 - Purpose: Programmatic access to Microsoft 365 (SharePoint / OneDrive / Teams) to read and optionally write project documents (.docx), extract Teams transcripts/comments/revision history, and perform automated processing (indexing, revision tracking, and RAG ingestion) for UT research/digital-twin workflows.
 - Anticipated go-live date: 2026-03-15
 - Purpose: Programmatic access to Microsoft 365 (SharePoint / OneDrive / Teams) to read and optionally write project documents (.docx), extract Teams transcripts/comments/revision history, and perform automated processing (indexing, revision tracking, and RAG ingestion) for UT research/digital-twin workflows.
 - Anticipated go-live date: 2026-03-13

### 2) Administrative / Owner Information
 - Department code: MECH
 - AUP signer: AUP_SIGNER_NAME bbooth@utexas.edu
 - Shared business email: neutronos-admin@utexas.edu (or SUBSTITUTE)
 - Shared technical email: neut-sense-tech@utexas.edu (or SUBSTITUTE)
 - Business owner 1: NAME <EMAIL>
 - Business owner 2: NAME <EMAIL>
 - Technical contact 1: Ben <ben@utexas.edu>
 - Technical contact 2: NAME <EMAIL>
 - Department code: DEPT_CODE_HERE  <!-- TODO: add numeric department code -->
 - AUP signer: AUP_SIGNER_NAME <AUP_SIGNER_EMAIL>  <!-- TODO: provide AUP signer -->
 - Shared business email: neutronos-admin@utexas.edu
 - Shared technical email: neut-sense-tech@utexas.edu
 - Business owner 1: BUSINESS_OWNER_1_NAME <BUSINESS_OWNER_1_EMAIL>  <!-- TODO -->
 - Business owner 2: BUSINESS_OWNER_2_NAME <BUSINESS_OWNER_2_EMAIL>  <!-- TODO -->
 - Technical contact 1: Ben <ben@utexas.edu>
 - Technical contact 2: TECH_CONTACT_2_NAME <TECH_CONTACT_2_EMAIL>  <!-- TODO -->

### 3) Vendor Information
- Vendor name: University of Texas / Internal development
- Contract reviewed by BCO: N/A (Internal). If using third-party vendors (Claude/Redpanda/OpenAI), provide contract links and BCO review status.
- Vendor docs: PROVIDE_LINK_OR_COPY_IF_APPLICABLE
 - Vendor name: University of Texas / Internal development
 - Contract reviewed by BCO: N/A (Internal). If using third-party vendors (Claude/Anthropic/Redpanda/OpenAI), provide contract links and BCO review status.
 - Vendor docs: PROVIDE_LINK_OR_COPY_IF_APPLICABLE

### 4) Customers / Population
- Who will be served: UT-affiliated research groups (faculty, staff, grad students) using NeutronOS.
- Will you authenticate guests/external users? No (initially). If yes, list external groups and justification.

### 5) Integration Technologies
- OpenID Connect (OIDC) / OAuth2: Yes (Authorization Code / delegated)
- Entra ID (Azure AD): Yes — App Registration & Service Principal required
- SAML: No
- Gallery / Enterprise App: Optional later

### 6) Customer Identifier
- Preferred identifier: UserPrincipalName (UPN) — confirm with IAM if they prefer `UT EID`.
 - Preferred identifier: UserPrincipalName (UPN) — confirm with IAM if they prefer `UT EID`.

### 7) Non-person Accounts
- Non-person accounts needed: Yes — Service Principal / App Registration for scheduled/background sync jobs (nightly ingestion). Initial interactive flows use delegated OAuth.
 - Non-person accounts needed: Yes — Service Principal / App Registration for scheduled/background sync jobs (nightly ingestion). Initial interactive flows use delegated OAuth.

### 8) Provisioning
- End-users: existing UT accounts (no provisioning required).
- Service principal: to be created by IAM as part of app registration.

### 9) Requested Attributes
- user.displayName, user.mail, user.userPrincipalName, user.id
- Optional: group membership claims (if you need AD group-based access control)

### 10) Graph API permissions (explain why)
- Delegated (user-consent) initially:
  - User.Read — basic profile for auth
  - Sites.Read.All — enumerate SharePoint sites / project libraries
  - Files.Read.All — read .docx from OneDrive/SharePoint for processing
  - Files.ReadWrite.All — OPTIONAL; write updated documents back after processing
  - Mail.Read — OPTIONAL future (calendar/email signals)
- Application (admin-consent) for future unattended jobs:
  - Files.Read.All / Files.ReadWrite.All (Application)
  - Sites.Read.All (Application)
  - User.Read.All (only if necessary)
 - Delegated (user-consent) initially:
 - User.Read — basic profile for auth
 - Sites.Read.All — enumerate SharePoint sites / project libraries
 - Files.Read.All — read .docx from OneDrive/SharePoint for processing
 - Files.ReadWrite.All — OPTIONAL; write updated documents back after processing (recommend NOT to request admin consent for this until you confirm need)
 - Mail.Read — OPTIONAL future (calendar/email signals)
 - Application (admin-consent) for future unattended jobs (requested later when background sync is enabled):
 - Files.Read.All / Files.ReadWrite.All (Application)
 - Sites.Read.All (Application)
 - User.Read.All (only if necessary)

### 11) Auth flow / Redirect URIs
- Initial auth: OAuth2 Authorization Code (OIDC) with delegated permissions (user-consent).
- Redirect URIs (examples — replace with exact values):
  - Production: https://neutronos.utexas.edu/auth/callback
  - Dev: http://localhost:8000/auth/callback
 - Initial auth: OAuth2 Authorization Code (OIDC) with delegated permissions (user-consent).
 - Redirect URIs (examples — replace with exact values):
 - Production: https://neutronos.utexas.edu/auth/callback  <!-- replace if different -->
 - Dev: http://localhost:8000/auth/callback

### 12) Data classification / compliance
- Data: research documents, meeting transcripts, comments, revision histories.
- Sensitive data: POSSIBLE — may contain FERPA/HIPAA/ITAR-relevant content depending on dataset; confirm and list if any dataset falls under these regimes.
- Secrets handling: client secrets/certs stored in Azure Key Vault or equivalent; rotate regularly; restrict access via IAM roles.
 - Data: research documents, meeting transcripts, comments, revision histories.
 - Sensitive data: POSSIBLE — may contain FERPA/HIPAA/ITAR-relevant content depending on dataset; confirm and list if any dataset falls under these regimes.
 - Secrets handling: client secrets/certs stored in Azure Key Vault or equivalent; rotate regularly; restrict access via IAM roles.

### 13) Suggested form text (copy/paste)
- Short description:
  "Neut Sense (a component/agent within the NeutronOS ecosystem) that programmatically ingests and processes OneDrive/SharePoint documents and Teams transcripts to automate indexing, revision-tracking, and RAG ingestion for UT research teams. Initial flow uses delegated OAuth; a service principal will be requested for future unattended syncs."
- Security controls:
  "Access limited to UT-affiliated users; least-privilege Graph scopes requested; app secrets stored in Azure Key Vault; admin audit logging enabled; application permissions will only be requested with IAM approval."
- Non-person account justification:
  "A service principal (non-person account) is required to run scheduled background sync jobs (nightly ingestion and transcript processing) that cannot rely on interactive user sessions."

### 14) Missing items (you must supply these before submitting)
- Department code (numeric)
- AUP signer name & email
- Confirm shared business & technical mailbox addresses (or create them)
- Names & emails for 2 business owners and 2 technical contacts
- Exact go-live date
- Exact redirect URI(s) (production and dev)
- Decision: Read-only (`Files.Read.All`) vs Read/Write (`Files.ReadWrite.All`)
- Decision: Request application permissions now (for background sync) or later
- Confirm if any datasets are subject to FERPA / HIPAA / ITAR (if yes, provide detail)
- Vendor contract links and BCO review status (if using external vendors)

### 15) Quick checklist
- [ ] DEPT code
- [ ] AUP signer
- [ ] Shared mailboxes confirmed
- [ ] 2 business owner contacts
- [ ] 2 technical contacts
- [ ] Go-live date
- [ ] Redirect URIs
- [ ] Read vs ReadWrite decision
- [ ] App-permissions now vs later
- [ ] Data classification confirmation
- [ ] Vendor contract docs (if applicable)
 - [ ] DEPT code
 - [ ] AUP signer
 - [ ] Shared mailboxes confirmed
 - [ ] 2 business owner contacts
 - [ ] 2 technical contacts
 - [ ] Go-live date (set to 2026-04-15 unless you prefer another)
 - [ ] Redirect URIs (confirm exact values)
 - [ ] Read vs ReadWrite decision (recommend start read-only)
 - [ ] App-permissions now vs later (recommend request app permissions later)
 - [ ] Data classification confirmation
 - [ ] Vendor contract docs (if applicable)

---

If you want, I can produce a single ready-to-paste block per form field (with placeholders filled from the checklist), or draft a brief email to Geoff to accelerate the IAM process.
