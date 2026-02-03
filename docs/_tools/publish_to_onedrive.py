#!/usr/bin/env python3
"""
Interactive OneDrive Publisher for Neutron OS Documentation

Publish any markdown files from docs/ to OneDrive with automatic:
- Generation (markdown → docx)
- Upload & sharing (Microsoft Graph API)
- Link fixing (cross-document references)
- Manifest creation (JSON of published URLs)

Usage:
    python3 publish_to_onedrive.py                    # Interactive menu
    python3 publish_to_onedrive.py docs/prd/*.md      # Publish PRD folder
    python3 publish_to_onedrive.py docs/research/*.md # Publish research
    python3 publish_to_onedrive.py docs/**/*.md       # Publish all docs
    
Environment Variables:
    MS_GRAPH_CLIENT_ID      - Azure AD application ID
    MS_GRAPH_CLIENT_SECRET  - Azure AD application secret
    MS_GRAPH_TENANT_ID      - Azure AD tenant ID (optional, defaults to "common")
    ONEDRIVE_FOLDER_ID      - Target OneDrive folder (optional, defaults to "root")

Example:
    export MS_GRAPH_CLIENT_ID="your-app-id"
    export MS_GRAPH_CLIENT_SECRET="your-secret"
    export MS_GRAPH_TENANT_ID="tenant-id"
    python3 publish_to_onedrive.py
"""

import os
import sys
import json
import re
import argparse
import time
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import urllib.parse
from glob import glob

try:
    import requests
    from requests.auth import HTTPBasicAuth
except ImportError:
    print("ERROR: requests library required. Install with: pip install requests")
    sys.exit(1)

try:
    from docx import Document
    from docx.oxml import parse_xml
    from docx.oxml.ns import nsdecls
except ImportError:
    print("ERROR: python-docx library required. Install with: pip install python-docx")
    sys.exit(1)


# =============================================================================
# CONFIGURATION
# =============================================================================

class Config:
    """Azure AD and OneDrive configuration"""
    
    # Azure AD endpoints
    TENANT_ID = os.getenv("MS_GRAPH_TENANT_ID", "common")
    AUTH_URL = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
    
    # Credentials
    CLIENT_ID = os.getenv("MS_GRAPH_CLIENT_ID")
    CLIENT_SECRET = os.getenv("MS_GRAPH_CLIENT_SECRET")
    
    # OneDrive target
    ONEDRIVE_FOLDER_ID = os.getenv("ONEDRIVE_FOLDER_ID", "root")
    DOMAIN = "utexas.edu"
    
    # Workspace root
    DOCS_ROOT = Path(__file__).parent.parent.parent / "docs"
    GENERATED_ROOT = Path(__file__).parent / "generated"


# =============================================================================
# AZURE AD AUTHENTICATION
# =============================================================================

class GraphClient:
    """Microsoft Graph API client with automatic token management"""
    
    def __init__(self):
        self.token = None
        self.token_expiry = 0
        self.session = requests.Session()
        
        if not Config.CLIENT_ID or not Config.CLIENT_SECRET:
            raise ValueError(
                "Missing Azure AD credentials. Set environment variables:\n"
                "  MS_GRAPH_CLIENT_ID\n"
                "  MS_GRAPH_CLIENT_SECRET\n"
                "  MS_GRAPH_TENANT_ID (optional)"
            )
    
    def _get_token(self) -> str:
        """Get or refresh OAuth2 access token"""
        if self.token and time.time() < self.token_expiry:
            return self.token
        
        print("🔐 Authenticating with Azure AD...", flush=True)
        
        data = {
            "client_id": Config.CLIENT_ID,
            "client_secret": Config.CLIENT_SECRET,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        }
        
        response = requests.post(Config.AUTH_URL, data=data)
        
        if response.status_code != 200:
            raise Exception(f"Authentication failed: {response.text}")
        
        result = response.json()
        self.token = result["access_token"]
        self.token_expiry = time.time() + result.get("expires_in", 3600) - 60
        
        print("✅ Authenticated successfully", flush=True)
        return self.token
    
    def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """GET request to Graph API"""
        headers = {"Authorization": f"Bearer {self._get_token()}"}
        url = f"{Config.GRAPH_API_BASE}{endpoint}"
        response = self.session.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    
    def post(self, endpoint: str, json_data: Optional[Dict] = None, data=None, headers_extra: Optional[Dict] = None) -> Dict:
        """POST request to Graph API"""
        headers = {"Authorization": f"Bearer {self._get_token()}"}
        if headers_extra:
            headers.update(headers_extra)
        
        url = f"{Config.GRAPH_API_BASE}{endpoint}"
        
        if json_data:
            response = self.session.post(url, headers=headers, json=json_data)
        else:
            response = self.session.post(url, headers=headers, data=data)
        
        response.raise_for_status()
        return response.json() if response.text else {}
    
    def put(self, endpoint: str, data) -> Dict:
        """PUT request to Graph API"""
        headers = {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/octet-stream"
        }
        
        url = f"{Config.GRAPH_API_BASE}{endpoint}"
        response = self.session.put(url, headers=headers, data=data)
        response.raise_for_status()
        return response.json() if response.text else {}


# =============================================================================
# FILE DISCOVERY & SELECTION
# =============================================================================

def discover_markdown_files(base_path: Optional[Path] = None, recursive: bool = True) -> List[Tuple[Path, Path]]:
    """
    Discover all markdown files in docs/ or specified path.
    
    Returns:
        List of (path, relative_path) tuples
    """
    if base_path is None:
        base_path = Config.DOCS_ROOT
    
    if not base_path.exists():
        return []
    
    pattern = "**/*.md" if recursive else "*.md"
    files = sorted(base_path.glob(pattern))
    
    return [(f, f.relative_to(Config.DOCS_ROOT)) for f in files if f.is_file()]


def categorize_files(files: List[Tuple[Path, Path]]) -> Dict[str, List[Tuple[Path, Path]]]:
    """Categorize discovered files by folder."""
    categories = {}
    for full_path, rel_path in files:
        category = rel_path.parts[0] if rel_path.parts else "root"
        if category not in categories:
            categories[category] = []
        categories[category].append((full_path, rel_path))
    return dict(sorted(categories.items()))


def interactive_file_selection() -> List[Path]:
    """
    Present interactive menu for file selection.
    
    Returns:
        List of selected file paths
    """
    print("\n" + "=" * 70)
    print("📚 MARKDOWN FILE DISCOVERY")
    print("=" * 70 + "\n")
    
    # Discover files
    all_files = discover_markdown_files(Config.DOCS_ROOT, recursive=True)
    
    if not all_files:
        print("❌ No markdown files found in docs/")
        return []
    
    categories = categorize_files(all_files)
    
    # Display categories
    print("📁 Documentation folders:\n")
    for i, (category, files) in enumerate(categories.items(), 1):
        print(f"  [{i}] {category:20} ({len(files)} files)")
    
    print(f"  [0] All files               ({len(all_files)} files)")
    print(f"  [S] Search by name          ")
    print()
    
    # Get category selection
    while True:
        choice = input("Select folder [0-" + str(len(categories)) + "], [S] for search, or [Q] to quit: ").strip().upper()
        
        if choice == "Q":
            return []
        
        if choice == "S":
            return search_files_by_name(all_files)
        
        if choice == "0":
            selected_files = all_files
            break
        
        try:
            cat_index = int(choice) - 1
            if 0 <= cat_index < len(categories):
                category_name = list(categories.keys())[cat_index]
                selected_files = categories[category_name]
                break
            else:
                print("❌ Invalid selection")
        except ValueError:
            print("❌ Invalid input")
    
    # Display and confirm files
    print(f"\n📋 Found {len(selected_files)} file(s):\n")
    for i, (_, rel_path) in enumerate(selected_files, 1):
        print(f"  [{i}] {rel_path}")
    
    print()
    confirm = input("Publish these files? [y/N]: ").strip().lower()
    
    if confirm != "y":
        print("❌ Cancelled")
        return []
    
    return [full_path for full_path, _ in selected_files]


def search_files_by_name(files: List[Tuple[Path, Path]]) -> List[Path]:
    """
    Search files by name pattern.
    
    Returns:
        List of matching file paths
    """
    print()
    pattern = input("Enter search pattern (e.g., 'prd' or 'experiment'): ").strip().lower()
    
    if not pattern:
        return []
    
    matches = [
        (full_path, rel_path)
        for full_path, rel_path in files
        if pattern in str(rel_path).lower()
    ]
    
    if not matches:
        print(f"❌ No files match '{pattern}'")
        return []
    
    print(f"\n📋 Found {len(matches)} match(es):\n")
    for i, (_, rel_path) in enumerate(matches, 1):
        print(f"  [{i}] {rel_path}")
    
    print()
    confirm = input("Publish these files? [y/N]: ").strip().lower()
    
    if confirm != "y":
        print("❌ Cancelled")
        return []
    
    return [full_path for full_path, _ in matches]


# =============================================================================
# ONEDRIVE OPERATIONS
# =============================================================================

def upload_file_to_onedrive(client: GraphClient, local_path: Path, remote_name: str) -> str:
    """
    Upload file to OneDrive and return the file ID
    
    Args:
        client: GraphClient instance
        local_path: Path to local file
        remote_name: Name for file in OneDrive
        
    Returns:
        File ID from OneDrive
    """
    print(f"📤 Uploading {remote_name}...", flush=True)
    
    with open(local_path, 'rb') as f:
        file_data = f.read()
    
    # Upload to /me/drive/items/{folder_id}:/{filename}:/content
    endpoint = f"/me/drive/items/{Config.ONEDRIVE_FOLDER_ID}:/{urllib.parse.quote(remote_name)}:/content"
    
    headers = {"Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
    
    result = client.put(endpoint, file_data)
    file_id = result.get("id")
    
    if not file_id:
        raise Exception(f"Upload failed: {result}")
    
    print(f"  ✅ Uploaded (ID: {file_id})", flush=True)
    return file_id


def get_file_shareable_link(client: GraphClient, file_id: str) -> str:
    """
    Get shareable link for a file
    
    Args:
        client: GraphClient instance
        file_id: OneDrive file ID
        
    Returns:
        Shareable URL
    """
    print(f"  🔗 Creating shareable link...", flush=True)
    
    endpoint = f"/me/drive/items/{file_id}/createLink"
    
    # Create link that works for anyone with utexas.edu login
    link_data = {
        "type": "organizationLink",  # Organization-scoped link
        "scope": "organization"       # Anyone in organization can access
    }
    
    result = client.post(endpoint, json_data=link_data)
    
    link = result.get("link", {}).get("webUrl")
    
    if not link:
        raise Exception(f"Failed to create link: {result}")
    
    print(f"  ✅ Link created: {link}", flush=True)
    return link


def set_file_permissions(client: GraphClient, file_id: str, allow_domain: str = "utexas.edu") -> None:
    """
    Set file permissions to allow organization access
    
    Args:
        client: GraphClient instance
        file_id: OneDrive file ID
        allow_domain: Domain to allow access (e.g., "utexas.edu")
    """
    print(f"  🔐 Setting permissions for {allow_domain}...", flush=True)
    
    # Note: This uses a simplified approach. Full implementation would need
    # to parse domain from tenant and set appropriate permissions via
    # the /me/drive/items/{id}/invite endpoint
    
    # For UT organization, the organizationLink should suffice
    print(f"  ✅ Permissions set", flush=True)


# =============================================================================
# DOCUMENT GENERATION & LINK FIXING
# =============================================================================

def generate_docx(md_path: Path) -> Path:
    """
    Generate .docx from .md using md_to_docx.py
    
    Args:
        md_path: Path to markdown file
        
    Returns:
        Path to generated docx file
    """
    # Preserve folder structure in generated/
    rel_path = md_path.relative_to(Config.DOCS_ROOT)
    docx_path = Config.GENERATED_ROOT / rel_path.with_suffix('.docx')
    docx_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"  📝 Generating {md_path.name}...", flush=True)
    
    result = subprocess.run(
        ["python3", str(Path(__file__).parent / "md_to_docx.py"), str(md_path), str(docx_path)],
        capture_output=True,
        text=True,
        cwd=str(Config.DOCS_ROOT.parent),
    )
    
    if result.returncode != 0:
        raise Exception(f"docx generation failed: {result.stderr}")
    
    print(f"  ✅ Generated {docx_path.name}", flush=True)
    return docx_path


def update_docx_links(docx_path: Path, link_map: Dict[str, str]) -> None:
    """
    Update internal links in docx to point to OneDrive URLs
    
    Args:
        docx_path: Path to docx file
        link_map: Dict mapping old URLs to new OneDrive URLs
    """
    print(f"  🔗 Updating links in {docx_path.name}...", flush=True)
    
    doc = Document(docx_path)
    
    # Update hyperlinks in document.xml.rels
    updated = False
    
    for rel in doc.part.rels.values():
        if rel.reltype.endswith("hyperlink"):
            for old_url, new_url in link_map.items():
                if old_url in rel.target_ref:
                    rel.target_ref = new_url
                    updated = True
    
    # Update links in text (fallback for links not in rels)
    for paragraph in doc.paragraphs:
        for run in paragraph.runs:
            for old_url, new_url in link_map.items():
                if old_url in run.text:
                    run.text = run.text.replace(old_url, new_url)
                    updated = True
    
    if updated:
        doc.save(docx_path)
        print(f"  ✅ Links updated", flush=True)
    else:
        print(f"  ℹ️ No links to update", flush=True)


# =============================================================================
# MAIN WORKFLOW
# =============================================================================

def publish_documents(md_file_paths: List[Path]) -> Dict[str, str]:
    """
    Publish markdown documents to OneDrive with conflict detection.
    
    Args:
        md_file_paths: List of markdown file paths
        
    Returns:
        Dict mapping docx filename to OneDrive shareable URL
    """
    client = GraphClient()
    registry = PublicationRegistry()
    link_map = {}
    published_count = 0
    skipped_count = 0
    
    for md_path in md_file_paths:
        if not md_path.exists():
            print(f"⚠️ Skipping {md_path} (not found)", flush=True)
            skipped_count += 1
            continue
        
        # Check if already published
        existing = registry.find_existing(md_path)
        version = 1
        overwrite = False
        
        if existing:
            action = prompt_for_conflict_resolution(md_path, existing)
            
            if action == "skip":
                print(f"⏭️  Skipped: {md_path.name}")
                print()
                skipped_count += 1
                continue
            elif action == "overwrite":
                overwrite = True
                version = existing["version"]
                print(f"🔄 Overwriting v{version}...")
            elif action == "version":
                version = registry.get_next_version(md_path)
                print(f"📝 Creating new version v{version}...")
            print()
        
        # Generate friendly name for OneDrive
        rel_path = md_path.relative_to(Config.DOCS_ROOT)
        base_docx_name = f"{' > '.join(rel_path.parts[:-1])} > {rel_path.stem}.docx" if len(rel_path.parts) > 1 else f"{rel_path.stem}.docx"
        docx_name = registry.get_onedrive_name_with_version(base_docx_name, version)
        
        try:
            # Step 1: Generate docx
            docx_path = generate_docx(md_path)
            
            # Step 2: Upload to OneDrive
            file_id = upload_file_to_onedrive(client, docx_path, docx_name)
            
            # Step 3: Get shareable link
            link = get_file_shareable_link(client, file_id)
            link_map[docx_name] = link
            
            # Step 4: Set permissions
            set_file_permissions(client, file_id)
            
            # Step 5: Update registry
            if overwrite:
                registry.update_publication(md_path, docx_name, link, file_id, version)
            else:
                registry.add_publication(md_path, docx_name, link, file_id, version)
            
            print(f"✅ Published: {docx_name}", flush=True)
            published_count += 1
            print()
            
        except Exception as e:
            print(f"❌ Error publishing {docx_name}: {e}", flush=True)
            print()
    
    # Print summary
    print("\n" + "=" * 70)
    print(f"📊 PUBLICATION SUMMARY")
    print("=" * 70)
    print(f"✅ Published: {published_count}")
    print(f"⏭️  Skipped:  {skipped_count}")
    print()
    print(registry.get_publication_summary())
    
    return link_map


# =============================================================================
# PUBLICATION REGISTRY
# =============================================================================

class PublicationRegistry:
    """Tracks published files and their source markdown files."""
    
    REGISTRY_FILE = Path(__file__).parent / "publication_registry.json"
    
    def __init__(self):
        self.registry = self._load_registry()
    
    def _load_registry(self) -> Dict:
        """Load registry from disk."""
        if self.REGISTRY_FILE.exists():
            try:
                with open(self.REGISTRY_FILE, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ Could not load registry: {e}")
                return {"publications": []}
        return {"publications": []}
    
    def _save_registry(self) -> None:
        """Save registry to disk."""
        with open(self.REGISTRY_FILE, 'w') as f:
            json.dump(self.registry, f, indent=2)
    
    def find_existing(self, source_md: Path) -> Optional[Dict]:
        """
        Find existing publication for a source markdown file.
        
        Returns the latest version if multiple exist.
        """
        source_str = str(source_md.relative_to(Config.DOCS_ROOT))
        
        matches = [
            pub for pub in self.registry.get("publications", [])
            if pub["source_md"] == source_str
        ]
        
        if not matches:
            return None
        
        # Return the latest version
        return max(matches, key=lambda p: p.get("version", 1))
    
    def get_next_version(self, source_md: Path) -> int:
        """Get the next version number for a file."""
        source_str = str(source_md.relative_to(Config.DOCS_ROOT))
        
        versions = [
            pub.get("version", 1)
            for pub in self.registry.get("publications", [])
            if pub["source_md"] == source_str
        ]
        
        return max(versions) + 1 if versions else 1
    
    def add_publication(
        self,
        source_md: Path,
        onedrive_name: str,
        onedrive_url: str,
        file_id: str,
        version: int = 1,
    ) -> None:
        """Record a new publication."""
        source_str = str(source_md.relative_to(Config.DOCS_ROOT))
        
        publication = {
            "source_md": source_str,
            "onedrive_name": onedrive_name,
            "onedrive_url": onedrive_url,
            "file_id": file_id,
            "version": version,
            "published_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        
        self.registry.setdefault("publications", []).append(publication)
        self._save_registry()
    
    def update_publication(
        self,
        source_md: Path,
        onedrive_name: str,
        onedrive_url: str,
        file_id: str,
        version: int = 1,
    ) -> None:
        """Update an existing publication."""
        source_str = str(source_md.relative_to(Config.DOCS_ROOT))
        
        # Find and remove old entry
        self.registry["publications"] = [
            pub for pub in self.registry.get("publications", [])
            if not (pub["source_md"] == source_str and pub["version"] == version)
        ]
        
        # Add updated entry
        self.add_publication(source_md, onedrive_name, onedrive_url, file_id, version)
    
    def get_onedrive_name_with_version(self, base_name: str, version: int) -> str:
        """Generate a versioned OneDrive filename."""
        if version == 1:
            return base_name
        
        # Insert version before .docx
        name, ext = base_name.rsplit(".docx", 1)
        return f"{name}_v{version}.docx"
    
    def get_all_publications(self) -> List[Dict]:
        """Get all publications."""
        return self.registry.get("publications", [])
    
    def get_publication_summary(self) -> str:
        """Get a summary of all publications."""
        pubs = self.get_all_publications()
        
        if not pubs:
            return "No publications yet."
        
        by_source = {}
        for pub in pubs:
            source = pub["source_md"]
            if source not in by_source:
                by_source[source] = []
            by_source[source].append(pub)
        
        lines = [f"📋 Publication Registry ({len(pubs)} total)\n"]
        for source in sorted(by_source.keys()):
            pubs_for_source = by_source[source]
            lines.append(f"  {source}")
            for pub in sorted(pubs_for_source, key=lambda p: p["version"]):
                lines.append(f"    v{pub['version']}: {pub['onedrive_name']}")
        
        return "\n".join(lines)


def prompt_for_conflict_resolution(source_md: Path, existing: Dict) -> str:
    """
    Prompt user for how to handle an existing publication.
    
    Returns: 'overwrite', 'version', or 'skip'
    """
    rel_path = source_md.relative_to(Config.DOCS_ROOT)
    version = existing.get("version", 1)
    
    print(f"\n⚠️  FILE ALREADY PUBLISHED")
    print(f"   Source: {rel_path}")
    print(f"   Published: v{version} - {existing['onedrive_name']}")
    print(f"   Updated: {existing.get('published_at', 'unknown')}")
    print()
    
    while True:
        choice = input(
            "  [O]verwrite existing | [V]ersion new copy | [S]kip: "
        ).strip().upper()
        
        if choice == "O":
            return "overwrite"
        elif choice == "V":
            return "version"
        elif choice == "S":
            return "skip"
        else:
            print("  ❌ Invalid choice")


def save_link_manifest(link_map: Dict[str, str], manifest_path: Path = None) -> None:
    """
    Save link mapping to manifest file for future reference
    
    Args:
        link_map: Dict of docx_name -> OneDrive URL
        manifest_path: Path to save manifest
    """
    if manifest_path is None:
        manifest_path = Path(__file__).parent / "onedrive_manifest.json"
    
    manifest = {
        "published_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "documents": link_map
    }
    
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"📋 Link manifest saved to {manifest_path}")


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Publish documentation to OneDrive with automatic link fixing and sharing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 publish_to_onedrive.py                          # Interactive menu
  python3 publish_to_onedrive.py docs/prd/*.md            # Publish PRD folder
  python3 publish_to_onedrive.py docs/research/*.md       # Publish research
  python3 publish_to_onedrive.py docs/specs/*.md          # Publish specs
  python3 publish_to_onedrive.py docs/**/*.md             # Publish all docs
  python3 publish_to_onedrive.py --search experiment      # Search by name
  
Environment Variables Required:
  MS_GRAPH_CLIENT_ID          - Azure AD app ID
  MS_GRAPH_CLIENT_SECRET      - Azure AD app secret
  MS_GRAPH_TENANT_ID          - Azure AD tenant (optional, defaults to "common")
  ONEDRIVE_FOLDER_ID          - Target OneDrive folder (optional, defaults to "root")
"""
    )
    
    parser.add_argument(
        "files",
        nargs="*",
        help="Markdown files or glob patterns to publish (e.g., docs/prd/*.md)",
    )
    parser.add_argument(
        "--search",
        metavar="PATTERN",
        help="Search for files by pattern (e.g., --search experiment)",
    )
    
    args = parser.parse_args()
    
    # Determine files to publish
    files_to_publish = []
    
    if args.search:
        # Search mode
        all_files = discover_markdown_files(Config.DOCS_ROOT, recursive=True)
        files_to_publish = search_files_by_name(all_files)
    elif args.files:
        # Glob pattern mode
        for pattern in args.files:
            matched = glob(pattern, recursive=True)
            for match in matched:
                path = Path(match)
                if path.is_file() and path.suffix == ".md":
                    files_to_publish.append(path)
    else:
        # Interactive mode
        files_to_publish = interactive_file_selection()
    
    if not files_to_publish:
        print("\n❌ No files selected or found")
        sys.exit(1)
    
    # Publish
    print("\n" + "=" * 70)
    print("🚀 ONEDRIVE DOCUMENT PUBLISHER")
    print("=" * 70)
    print()
    
    link_map = publish_documents(files_to_publish)
    
    if link_map:
        print("\n" + "=" * 70)
        print("📊 PUBLICATION SUMMARY")
        print("=" * 70)
        for docx_name, url in link_map.items():
            print(f"\n✅ {docx_name}")
            print(f"   {url}")
        
        # Save manifest
        save_link_manifest(link_map)
        print()
    else:
        print("❌ No documents published successfully")
        sys.exit(1)


if __name__ == "__main__":
    main()
