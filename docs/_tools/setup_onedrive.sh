#!/bin/bash
#
# Interactive setup script for OneDrive publishing
# Helps configure Azure AD credentials and test the connection
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║           Neutron OS OneDrive Publishing Setup                    ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo

# Check if .env exists
if [ -f .env ]; then
    echo -e "${YELLOW}Found existing .env file${NC}"
    read -p "Overwrite? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Using existing .env"
        source .env
    fi
fi

# Interactive credential entry
echo -e "${BLUE}Enter Azure AD credentials:${NC}"
echo

read -p "Client ID (from Azure Portal): " CLIENT_ID
read -sp "Client Secret (paste carefully): " CLIENT_SECRET
echo
read -p "Tenant ID (e.g., utexas.onmicrosoft.com, or 'common'): " TENANT_ID
read -p "OneDrive Folder ID (press Enter for 'root'): " FOLDER_ID

FOLDER_ID=${FOLDER_ID:-root}
TENANT_ID=${TENANT_ID:-common}

# Validate inputs
if [ -z "$CLIENT_ID" ] || [ -z "$CLIENT_SECRET" ]; then
    echo -e "${RED}Error: Client ID and Secret are required${NC}"
    exit 1
fi

echo
echo -e "${YELLOW}Configuration:${NC}"
echo "  Client ID: ${CLIENT_ID:0:20}..."
echo "  Client Secret: ••••••••••••••••••"
echo "  Tenant ID: $TENANT_ID"
echo "  Folder ID: $FOLDER_ID"
echo

read -p "Save to .env file? (y/n) " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    cat > .env << EOF
MS_GRAPH_CLIENT_ID=$CLIENT_ID
MS_GRAPH_CLIENT_SECRET=$CLIENT_SECRET
MS_GRAPH_TENANT_ID=$TENANT_ID
ONEDRIVE_FOLDER_ID=$FOLDER_ID
EOF
    echo -e "${GREEN}✓ Saved to .env${NC}"
    
    # Add .env to .gitignore if not already there
    if ! grep -q "^.env$" .gitignore 2>/dev/null; then
        echo ".env" >> .gitignore
        echo -e "${GREEN}✓ Added .env to .gitignore${NC}"
    fi
else
    # Set as environment variables for this session
    export MS_GRAPH_CLIENT_ID=$CLIENT_ID
    export MS_GRAPH_CLIENT_SECRET=$CLIENT_SECRET
    export MS_GRAPH_TENANT_ID=$TENANT_ID
    export ONEDRIVE_FOLDER_ID=$FOLDER_ID
    echo -e "${YELLOW}Note: Credentials set for this session only${NC}"
fi

echo
echo -e "${BLUE}Testing connection...${NC}"
echo

# Test the connection
python3 << 'PYEOF'
import os
import sys

# Add docs._tools to path
sys.path.insert(0, os.path.join(os.getcwd(), 'docs', '_tools'))

try:
    from publish_to_onedrive import GraphClient, Config
    
    print("  Credentials configured:")
    print(f"    • Client ID: {Config.CLIENT_ID[:20]}..." if Config.CLIENT_ID else "    • Client ID: NOT SET")
    print(f"    • Client Secret: {'SET' if Config.CLIENT_SECRET else 'NOT SET'}")
    print(f"    • Tenant ID: {Config.TENANT_ID}")
    print(f"    • Folder ID: {Config.ONEDRIVE_FOLDER_ID}")
    print()
    
    if not Config.CLIENT_ID or not Config.CLIENT_SECRET:
        print("\033[0;31m✗ Credentials incomplete\033[0m")
        sys.exit(1)
    
    print("  Authenticating...")
    client = GraphClient()
    
    print("  Testing API access...")
    result = client.get("/me")
    user_id = result.get("id")
    user_name = result.get("displayName")
    
    print(f"\033[0;32m✓ Success!\033[0m")
    print(f"    Authenticated as: {user_name} ({user_id})")
    print()
    
    # Show OneDrive info
    drive = client.get("/me/drive")
    quota = drive.get("quota", {})
    used = quota.get("used", 0)
    total = quota.get("total", 0)
    
    if total > 0:
        used_pct = (used / total) * 100
        print(f"  OneDrive Storage:")
        print(f"    Used: {used / (1024**3):.1f} GB / {total / (1024**3):.1f} GB ({used_pct:.1f}%)")
    
    print()
    print("\033[0;34m🚀 Ready to publish!\033[0m")
    print("   Run: python3 docs/_tools/publish_to_onedrive.py --prd")
    
except Exception as e:
    print(f"\033[0;31m✗ Connection failed: {e}\033[0m")
    print()
    print("Troubleshooting:")
    print("  1. Verify credentials in Azure Portal")
    print("  2. Ensure app has Files.ReadWrite.All permission")
    print("  3. Check that admin consent was granted")
    sys.exit(1)

PYEOF

echo
