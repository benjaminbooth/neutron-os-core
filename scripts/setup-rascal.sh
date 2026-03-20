#!/usr/bin/env bash
# setup-rascal.sh — One-shot k3d + Helm bootstrap for the Rascal server
#
# Installs k3d (containerd runtime), creates the "rascal" cluster, deploys
# the neutron-os Helm chart with Rascal values (PostgreSQL + Ollama + GPU).
#
# Prerequisites on the Rascal host (Ubuntu 22.04/24.04):
#   - NVIDIA driver installed (nvidia-smi should work)
#   - sudo / root access
#   - UT VPN active
#
# Usage:
#   # On your laptop (SSH into Rascal first):
#   ssh <rascal-user>@10.159.142.118
#
#   # Then on Rascal:
#   git clone <repo> && cd Neutron_OS
#   DB_PASS=<secret> POSTGRES_PASS=<secret> bash scripts/setup-rascal.sh
#
# Environment variables:
#   DB_PASS          — PostgreSQL neut user password (required)
#   POSTGRES_PASS    — PostgreSQL superuser password (required)
#   CLUSTER_NAME     — k3d cluster name (default: rascal)
#   NAMESPACE        — Kubernetes namespace (default: neut)
#   RELEASE_NAME     — Helm release name (default: neut)
#   SKIP_K3D_INSTALL — Set to 1 to skip k3d installation (if already installed)
#   SKIP_NVIDIA      — Set to 1 to skip NVIDIA toolkit check

set -euo pipefail

CLUSTER_NAME="${CLUSTER_NAME:-rascal}"
NAMESPACE="${NAMESPACE:-neut}"
RELEASE_NAME="${RELEASE_NAME:-neut}"
SKIP_K3D_INSTALL="${SKIP_K3D_INSTALL:-0}"
SKIP_NVIDIA="${SKIP_NVIDIA:-0}"

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CHART_DIR="${REPO_ROOT}/infra/helm/charts/neutron-os"
VALUES_RASCAL="${CHART_DIR}/values-rascal.yaml"

: "${DB_PASS:?DB_PASS is required (PostgreSQL neut user password)}"
: "${POSTGRES_PASS:?POSTGRES_PASS is required (PostgreSQL superuser password)}"

echo "========================================================"
echo "  NeutronOS — Rascal Server Bootstrap"
echo "  Cluster:   ${CLUSTER_NAME}"
echo "  Namespace: ${NAMESPACE}"
echo "  Release:   ${RELEASE_NAME}"
echo "========================================================"
echo ""

# -------------------------------------------------------
# 1. Install dependencies
# -------------------------------------------------------
echo "[1/7] Checking dependencies..."

install_if_missing() {
  local cmd="$1" install_cmd="$2"
  if ! command -v "${cmd}" &>/dev/null; then
    echo "       Installing ${cmd}..."
    eval "${install_cmd}"
  else
    echo "       ${cmd} already installed: $(${cmd} --version 2>&1 | head -1)"
  fi
}

install_if_missing curl   "apt-get install -y curl"
install_if_missing kubectl "curl -sLO https://dl.k8s.io/release/\$(curl -sL https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl && chmod +x kubectl && mv kubectl /usr/local/bin/"
install_if_missing helm   "curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash"

if [[ "${SKIP_K3D_INSTALL}" != "1" ]]; then
  install_if_missing k3d "curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash"
fi

# -------------------------------------------------------
# 2. NVIDIA container toolkit
# -------------------------------------------------------
echo "[2/7] Checking NVIDIA container toolkit..."

if [[ "${SKIP_NVIDIA}" != "1" ]]; then
  if ! command -v nvidia-smi &>/dev/null; then
    echo "       [WARN] nvidia-smi not found. GPU acceleration will not work."
    echo "              Install NVIDIA drivers before deploying Ollama with GPU."
  else
    GPU_INFO=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null | head -1)
    echo "       GPU detected: ${GPU_INFO}"

    if ! dpkg -l | grep -q nvidia-container-toolkit 2>/dev/null; then
      echo "       Installing nvidia-container-toolkit (required for k3d GPU passthrough)..."
      curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
      curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
        sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
        tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
      apt-get update -qq
      apt-get install -y nvidia-container-toolkit
      nvidia-ctk runtime configure --runtime=containerd
      systemctl restart containerd 2>/dev/null || true
      echo "       nvidia-container-toolkit installed."
    else
      echo "       nvidia-container-toolkit already installed."
    fi
  fi
else
  echo "       Skipping NVIDIA check (SKIP_NVIDIA=1)"
fi

# -------------------------------------------------------
# 3. Create k3d cluster
# -------------------------------------------------------
echo "[3/7] Setting up k3d cluster '${CLUSTER_NAME}'..."

if k3d cluster list | grep -q "^${CLUSTER_NAME}"; then
  echo "       Cluster '${CLUSTER_NAME}' already exists."
else
  echo "       Creating k3d cluster '${CLUSTER_NAME}'..."
  k3d cluster create "${CLUSTER_NAME}" \
    --servers 1 \
    --agents 0 \
    --k3s-arg "--disable=traefik@server:0" \
    --k3s-arg "--disable=metrics-server@server:0" \
    --no-lb \
    --wait
  echo "       Cluster '${CLUSTER_NAME}' created."
fi

# Merge kubeconfig
k3d kubeconfig merge "${CLUSTER_NAME}" --kubeconfig-merge-default
kubectl config use-context "k3d-${CLUSTER_NAME}"
echo "       Using context: k3d-${CLUSTER_NAME}"

# -------------------------------------------------------
# 4. Install NVIDIA device plugin (if GPU available)
# -------------------------------------------------------
echo "[4/7] Checking NVIDIA device plugin..."

if [[ "${SKIP_NVIDIA}" != "1" ]] && command -v nvidia-smi &>/dev/null; then
  if ! kubectl get daemonset -n kube-system nvidia-device-plugin-daemonset &>/dev/null 2>&1; then
    echo "       Installing NVIDIA device plugin..."
    kubectl create -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.14.5/nvidia-device-plugin.yml || true
    echo "       NVIDIA device plugin deployed. Allow ~60s for nodes to report GPU capacity."
  else
    echo "       NVIDIA device plugin already installed."
  fi
else
  echo "       Skipping NVIDIA device plugin (no GPU or SKIP_NVIDIA=1)."
fi

# -------------------------------------------------------
# 5. Add Helm dependencies (bitnami for postgresql)
# -------------------------------------------------------
echo "[5/7] Updating Helm dependencies..."

helm repo add bitnami https://charts.bitnami.com/bitnami 2>/dev/null || true
helm repo update
helm dependency update "${CHART_DIR}"

# -------------------------------------------------------
# 6. Deploy Helm chart
# -------------------------------------------------------
echo "[6/7] Deploying neutron-os Helm chart..."

kubectl create namespace "${NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -

helm upgrade --install "${RELEASE_NAME}" "${CHART_DIR}" \
  --namespace "${NAMESPACE}" \
  --values "${VALUES_RASCAL}" \
  --set "postgresql.auth.password=${DB_PASS}" \
  --set "postgresql.auth.postgresPassword=${POSTGRES_PASS}" \
  --timeout 10m \
  --wait \
  --wait-for-jobs

echo "       Helm release '${RELEASE_NAME}' deployed to namespace '${NAMESPACE}'."

# -------------------------------------------------------
# 7. Print access info
# -------------------------------------------------------
echo "[7/7] Deployment complete!"
echo ""
echo "========================================================"
echo "  Cluster:  k3d-${CLUSTER_NAME}"
echo "  Namespace: ${NAMESPACE}"
echo "  Release:  ${RELEASE_NAME}"
echo "========================================================"
echo ""
echo "  PostgreSQL (port-forward to access):"
echo "    kubectl port-forward -n ${NAMESPACE} svc/${RELEASE_NAME}-postgresql 5432:5432"
echo "    postgresql://neut:<password>@localhost:5432/neut_db"
echo ""
echo "  Ollama (NodePort — accessible from UT VPN):"
echo "    http://10.159.142.118:31434"
echo "    curl http://10.159.142.118:31434/api/tags"
echo ""
echo "  To check pod status:"
echo "    kubectl get pods -n ${NAMESPACE}"
echo ""
echo "  To check Ollama model pull progress:"
echo "    kubectl logs -n ${NAMESPACE} -l app.kubernetes.io/component=ollama -c pull-models -f"
echo ""
echo "  To add Qwen as an LLM provider (after confirming model tag):"
echo "    Edit runtime/config/llm-providers.toml, uncomment qwen-rascal block"
echo "    Confirm model tag: curl http://10.159.142.118:31434/api/tags | python3 -m json.tool"
echo ""
