# DocFlow Infrastructure Implementation Guide

> Step-by-step guide to stand up DocFlow infrastructure from zero to production.

**Estimated Timeline:**
- Phase 1 (Local): 1-2 hours
- Phase 2 (GitLab CI/CD): 2-4 hours  
- Phase 3 (AWS Staging): 4-8 hours
- Phase 4 (AWS Production): 4-8 hours
- Phase 5 (Open Source Prep): 2-4 hours

---

## Phase 1: Local Development Environment

**Goal:** Full DocFlow stack running on your laptop with K3D.

### 1.1 One-Step Setup (Recommended)

The bootstrap script handles everything automatically:

```bash
cd /Users/ben/Projects/UT_Computational_NE/Neutron_OS/docs/_tools/docflow
./bootstrap.sh
```

- [ ] **Run bootstrap script**
  - Checks for and installs missing dependencies
  - Creates K3D cluster with local registry
  - Deploys PostgreSQL (with pgvector), Redis, and Ollama
  - Verifies all services are healthy
  
  Use `./bootstrap.sh --dry-run` to preview first.

- [ ] **Install Python package**
  ```bash
  pip install -e ".[dev]"
  ```

- [ ] **Skip to [1.3 Run Local Tests](#13-run-local-tests)**

---

### 1.1b Manual Prerequisites (Alternative)

If you prefer manual setup, install each dependency:

```bash
# Check what's already installed
which docker kubectl k3d helm terraform
```

- [ ] **Install Docker Desktop**
  ```bash
  # macOS
  brew install --cask docker
  # Then launch Docker Desktop from Applications
  ```

- [ ] **Install kubectl**
  ```bash
  brew install kubectl
  ```

- [ ] **Install K3D**
  ```bash
  brew install k3d
  ```

- [ ] **Install Helm**
  ```bash
  brew install helm
  ```

- [ ] **Install Terraform**
  ```bash
  brew install terraform
  ```

- [ ] **Install AWS CLI**
  ```bash
  brew install awscli
  ```

- [ ] **Verify installations**
  ```bash
  docker --version
  kubectl version --client
  k3d version
  helm version
  terraform version
  aws --version
  ```

### 1.2 Start Local Cluster (Manual Path)

- [ ] **Create K3D cluster**
  ```bash
  cd /Users/ben/Projects/UT_Computational_NE/Neutron_OS/docs/_tools/docflow
  ./scripts/local-dev.sh start
  ```
  
  This will:
  - Create K3D cluster with local registry
  - Install NGINX ingress controller
  - Deploy PostgreSQL with pgvector
  - Deploy Redis
  - Deploy Ollama (local LLM)
  - Build and deploy DocFlow

- [ ] **Verify cluster is running**
  ```bash
  kubectl get pods -n docflow
  # All pods should be Running
  ```

- [ ] **Test API health**
  ```bash
  curl http://localhost:8080/health
  # Should return: {"status": "healthy"}
  ```

- [ ] **Test database connection**
  ```bash
  ./scripts/local-dev.sh shell db
  # In psql:
  \dx  # Should show vector extension
  \q
  ```

### 1.3 Run Local Tests

- [ ] **Install Python dependencies**
  ```bash
  cd /Users/ben/Projects/UT_Computational_NE/Neutron_OS/docs/_tools/docflow
  python -m venv .venv
  source .venv/bin/activate
  pip install -e ".[dev]"
  ```

- [ ] **Run unit tests**
  ```bash
  pytest tests/unit/ -v
  ```

- [ ] **Run integration tests against local cluster**
  ```bash
  DATABASE_URL=postgresql://docflow:localdev@localhost:5432/docflow \
  pytest tests/integration/ -v
  ```

### 1.4 Local Development Workflow

- [ ] **Make a code change and redeploy**
  ```bash
  cd deploy/k3d
  make build-images
  make deploy-app
  ```

- [ ] **View logs**
  ```bash
  ./scripts/local-dev.sh logs api
  ./scripts/local-dev.sh logs agent
  ```

- [ ] **Stop cluster when done (preserves data)**
  ```bash
  ./scripts/local-dev.sh stop
  ```

**✅ Phase 1 Complete when:** Local cluster runs, tests pass, you can make changes and redeploy.

---

## Phase 2: GitLab CI/CD Setup

**Goal:** Automated testing, building, and deployment pipeline.

### 2.1 GitLab Project Setup

- [ ] **Create GitLab project** (if not exists)
  - Go to your GitLab instance
  - Create new project: `neutron-os/docflow`
  - Set visibility: Private

- [ ] **Push code to GitLab**
  ```bash
  cd /Users/ben/Projects/UT_Computational_NE/Neutron_OS/docs/_tools/docflow
  git init  # if not already
  git remote add origin git@gitlab.example.com:neutron-os/docflow.git
  git add .
  git commit -m "Initial DocFlow commit"
  git push -u origin main
  ```

### 2.2 GitLab Container Registry

- [ ] **Enable Container Registry**
  - GitLab Project → Settings → General → Visibility
  - Enable "Container Registry"

- [ ] **Test registry access**
  ```bash
  docker login registry.gitlab.example.com
  # Use your GitLab username and a Personal Access Token with registry scope
  ```

### 2.3 GitLab Package Registry

- [ ] **Enable Package Registry**
  - GitLab Project → Settings → General → Visibility
  - Enable "Package Registry"

- [ ] **Test PyPI registry** (optional, for Python packages)
  ```bash
  # Create a test .pypirc
  cat > ~/.pypirc << 'EOF'
  [distutils]
  index-servers = gitlab
  
  [gitlab]
  repository = https://gitlab.example.com/api/v4/projects/PROJECT_ID/packages/pypi
  username = __token__
  password = YOUR_PERSONAL_ACCESS_TOKEN
  EOF
  ```

### 2.4 CI/CD Variables

- [ ] **Navigate to CI/CD Settings**
  - GitLab Project → Settings → CI/CD → Variables

- [ ] **Add AWS credentials** (for stage/prod deployment)
  | Variable | Value | Protected | Masked |
  |----------|-------|-----------|--------|
  | `AWS_ACCESS_KEY_ID` | Your AWS access key | ✓ | ✓ |
  | `AWS_SECRET_ACCESS_KEY` | Your AWS secret key | ✓ | ✓ |
  | `AWS_REGION` | `us-east-1` | ✓ | ✗ |

- [ ] **Add Helm repository credentials** (if using private Helm repo)
  | Variable | Value | Protected | Masked |
  |----------|-------|-----------|--------|
  | `HELM_REPO_URL` | Your Helm repo URL | ✓ | ✗ |
  | `HELM_REPO_USERNAME` | Username | ✓ | ✓ |
  | `HELM_REPO_PASSWORD` | Password | ✓ | ✓ |

### 2.5 GitLab Runners

- [ ] **Check available runners**
  - GitLab Project → Settings → CI/CD → Runners
  - Ensure you have runners with Docker executor

- [ ] **Or register a new runner** (if needed)
  ```bash
  # On a machine with Docker
  docker run -d --name gitlab-runner --restart always \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v gitlab-runner-config:/etc/gitlab-runner \
    gitlab/gitlab-runner:latest
  
  docker exec -it gitlab-runner gitlab-runner register
  # Follow prompts, select "docker" executor
  ```

### 2.6 Test CI Pipeline

- [ ] **Trigger first pipeline**
  ```bash
  git commit --allow-empty -m "Trigger CI"
  git push
  ```

- [ ] **Monitor pipeline**
  - GitLab Project → CI/CD → Pipelines
  - Watch for test, lint, and build stages

- [ ] **Fix any failures**
  - Check job logs for errors
  - Common issues:
    - Missing dependencies in Dockerfile
    - Test failures
    - Registry authentication

- [ ] **Verify images in registry**
  - GitLab Project → Packages & Registries → Container Registry
  - Should see `docflow/api` and `docflow/agent` images

**✅ Phase 2 Complete when:** Pipeline runs green, images are pushed to registry.

---

## Phase 3: AWS Staging Environment

**Goal:** Fully functional staging environment on AWS EKS.

### 3.1 AWS Account Setup

- [ ] **Create AWS account** (if needed)
  - https://aws.amazon.com/
  - Enable MFA on root account

- [ ] **Create IAM user for Terraform**
  ```bash
  # Or via AWS Console: IAM → Users → Add User
  aws iam create-user --user-name terraform-docflow
  ```

- [ ] **Attach required policies**
  ```bash
  # Create policy document
  cat > /tmp/terraform-policy.json << 'EOF'
  {
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Action": [
          "ec2:*",
          "eks:*",
          "rds:*",
          "elasticache:*",
          "s3:*",
          "secretsmanager:*",
          "iam:*",
          "logs:*",
          "cloudwatch:*",
          "autoscaling:*",
          "elasticloadbalancing:*",
          "kms:*"
        ],
        "Resource": "*"
      }
    ]
  }
  EOF
  
  aws iam create-policy \
    --policy-name TerraformDocflow \
    --policy-document file:///tmp/terraform-policy.json
  
  aws iam attach-user-policy \
    --user-name terraform-docflow \
    --policy-arn arn:aws:iam::YOUR_ACCOUNT_ID:policy/TerraformDocflow
  ```

- [ ] **Create access keys**
  ```bash
  aws iam create-access-key --user-name terraform-docflow
  # Save the AccessKeyId and SecretAccessKey securely!
  ```

- [ ] **Configure AWS CLI**
  ```bash
  aws configure --profile docflow
  # Enter: Access Key ID, Secret Access Key, Region (us-east-1), Output (json)
  
  # Set as default for this session
  export AWS_PROFILE=docflow
  ```

### 3.2 Terraform State Backend

- [ ] **Create S3 bucket for state**
  ```bash
  aws s3 mb s3://docflow-terraform-state-YOUR_ACCOUNT_ID --region us-east-1
  
  # Enable versioning
  aws s3api put-bucket-versioning \
    --bucket docflow-terraform-state-YOUR_ACCOUNT_ID \
    --versioning-configuration Status=Enabled
  
  # Enable encryption
  aws s3api put-bucket-encryption \
    --bucket docflow-terraform-state-YOUR_ACCOUNT_ID \
    --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
  ```

- [ ] **Create DynamoDB table for state locking**
  ```bash
  aws dynamodb create-table \
    --table-name docflow-terraform-locks \
    --attribute-definitions AttributeName=LockID,AttributeType=S \
    --key-schema AttributeName=LockID,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region us-east-1
  ```

- [ ] **Update Terraform backend config**
  ```bash
  # Edit deploy/terraform/environments/stage/main.tf
  # Uncomment the backend "s3" block and update:
  # - bucket = "docflow-terraform-state-YOUR_ACCOUNT_ID"
  ```

### 3.3 Deploy Staging Infrastructure

- [ ] **Initialize Terraform**
  ```bash
  cd /Users/ben/Projects/UT_Computational_NE/Neutron_OS/docs/_tools/docflow/deploy/terraform/environments/stage
  terraform init
  ```

- [ ] **Review the plan**
  ```bash
  terraform plan -out=stage.tfplan
  # Review resources to be created:
  # - VPC with public/private subnets
  # - EKS cluster
  # - RDS PostgreSQL
  # - ElastiCache Redis
  # - Security groups
  # - IAM roles
  ```

- [ ] **Apply infrastructure** (takes 15-20 minutes)
  ```bash
  terraform apply stage.tfplan
  ```

- [ ] **Save outputs**
  ```bash
  terraform output > stage-outputs.txt
  ```

### 3.4 Configure kubectl for EKS

- [ ] **Update kubeconfig**
  ```bash
  aws eks update-kubeconfig --name docflow-stage --region us-east-1
  ```

- [ ] **Verify cluster access**
  ```bash
  kubectl get nodes
  # Should show 2 nodes
  ```

- [ ] **Verify namespace and secrets**
  ```bash
  kubectl get namespaces
  kubectl get secrets -n docflow
  # Should see docflow-db-credentials
  ```

### 3.5 Install Additional Components

- [ ] **Install cert-manager** (for TLS)
  ```bash
  helm repo add jetstack https://charts.jetstack.io
  helm repo update
  
  helm install cert-manager jetstack/cert-manager \
    --namespace cert-manager \
    --create-namespace \
    --set installCRDs=true
  ```

- [ ] **Install NGINX Ingress Controller**
  ```bash
  helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
  
  helm install ingress-nginx ingress-nginx/ingress-nginx \
    --namespace ingress-nginx \
    --create-namespace \
    --set controller.service.type=LoadBalancer
  ```

- [ ] **Get Load Balancer DNS**
  ```bash
  kubectl get svc -n ingress-nginx ingress-nginx-controller \
    -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'
  # Note this hostname for DNS setup
  ```

### 3.6 DNS Setup

- [ ] **Create Route 53 hosted zone** (or use existing)
  ```bash
  aws route53 create-hosted-zone \
    --name docflow-stage.example.com \
    --caller-reference $(date +%s)
  ```

- [ ] **Create A record pointing to Load Balancer**
  - Route 53 → Hosted Zone → Create Record
  - Record type: A
  - Alias: Yes
  - Route traffic to: Application Load Balancer
  - Select the ELB from the dropdown

### 3.7 Enable pgvector on RDS

- [ ] **Connect to RDS and enable extension**
  ```bash
  # Get RDS endpoint from Terraform output
  PGHOST=$(terraform output -raw rds_endpoint | cut -d: -f1)
  PGPASSWORD=$(aws secretsmanager get-secret-value \
    --secret-id docflow-stage/rds-credentials \
    --query SecretString --output text | jq -r .password)
  
  # Connect and enable
  PGPASSWORD=$PGPASSWORD psql -h $PGHOST -U docflow -d docflow << 'EOF'
  CREATE EXTENSION IF NOT EXISTS vector;
  CREATE EXTENSION IF NOT EXISTS pg_trgm;
  CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
  \dx
  EOF
  ```

### 3.8 Deploy DocFlow to Staging

- [ ] **Trigger staging deployment**
  ```bash
  # Push to main branch
  git add .
  git commit -m "Deploy to staging"
  git push origin main
  ```

- [ ] **Monitor GitLab pipeline**
  - Watch the `deploy:stage` job
  - Check logs for any errors

- [ ] **Or deploy manually**
  ```bash
  helm upgrade --install docflow deploy/helm/docflow \
    --namespace docflow \
    --values deploy/helm/docflow/values-stage.yaml \
    --set api.image.tag=latest \
    --set agent.image.tag=latest \
    --wait
  ```

### 3.9 Verify Staging Deployment

- [ ] **Check pods**
  ```bash
  kubectl get pods -n docflow
  # All should be Running
  ```

- [ ] **Check services**
  ```bash
  kubectl get svc -n docflow
  ```

- [ ] **Test API**
  ```bash
  curl https://docflow-stage.example.com/health
  ```

- [ ] **Run integration tests against staging**
  ```bash
  pytest tests/integration/ --env=stage
  ```

**✅ Phase 3 Complete when:** Staging environment is running and accessible via DNS.

---

## Phase 4: AWS Production Environment

**Goal:** Production-ready environment with high availability and blue/green deployments.

### 4.1 Create Production Terraform Config

- [ ] **Copy stage config to prod**
  ```bash
  cp -r deploy/terraform/environments/stage deploy/terraform/environments/prod
  ```

- [ ] **Update prod configuration**
  Edit `deploy/terraform/environments/prod/main.tf`:
  - Change `environment = "prod"`
  - Enable Multi-AZ for RDS: `multi_az = true`
  - Use larger instance types
  - Enable deletion protection
  - Configure 3 AZs instead of 2

### 4.2 Production-Specific Changes

- [ ] **Update values-prod.yaml**
  Create/update `deploy/helm/docflow/values-prod.yaml`:
  ```yaml
  environment: production
  
  replicaCount:
    api: 3
    agent: 2
  
  api:
    resources:
      requests:
        memory: 512Mi
        cpu: 250m
      limits:
        memory: 1Gi
        cpu: 1000m
  
  blueGreen:
    enabled: true
    activeColor: blue
  
  autoscaling:
    enabled: true
    api:
      minReplicas: 3
      maxReplicas: 10
    agent:
      minReplicas: 2
      maxReplicas: 5
  
  podDisruptionBudget:
    enabled: true
    api:
      minAvailable: 2
    agent:
      minAvailable: 1
  ```

### 4.3 Deploy Production Infrastructure

- [ ] **Initialize and apply Terraform**
  ```bash
  cd deploy/terraform/environments/prod
  terraform init
  terraform plan -out=prod.tfplan
  # Review carefully!
  terraform apply prod.tfplan
  ```

- [ ] **Configure kubectl for prod**
  ```bash
  aws eks update-kubeconfig --name docflow-prod --region us-east-1
  ```

### 4.4 Production DNS and TLS

- [ ] **Create production DNS record**
  - Route 53 → Create A record for `docflow.example.com`
  - Point to production Load Balancer

- [ ] **Configure Let's Encrypt for TLS**
  ```bash
  kubectl apply -f - << 'EOF'
  apiVersion: cert-manager.io/v1
  kind: ClusterIssuer
  metadata:
    name: letsencrypt-prod
  spec:
    acme:
      server: https://acme-v02.api.letsencrypt.org/directory
      email: your-email@example.com
      privateKeySecretRef:
        name: letsencrypt-prod
      solvers:
        - http01:
            ingress:
              class: nginx
  EOF
  ```

### 4.5 Blue/Green Deployment Setup

- [ ] **Deploy initial "green" version**
  ```bash
  helm upgrade --install docflow-green deploy/helm/docflow \
    --namespace docflow-prod \
    --values deploy/helm/docflow/values-prod.yaml \
    --set blueGreen.enabled=true \
    --set blueGreen.activeColor=green \
    --set api.image.tag=v0.1.0 \
    --set agent.image.tag=v0.1.0
  ```

- [ ] **Create service pointing to green**
  ```bash
  kubectl apply -f - << 'EOF'
  apiVersion: v1
  kind: Service
  metadata:
    name: docflow-api
    namespace: docflow-prod
  spec:
    selector:
      app.kubernetes.io/name: docflow
      app.kubernetes.io/component: api
      docflow.io/color: green
    ports:
      - port: 80
        targetPort: 8080
  EOF
  ```

### 4.6 Production Deployment Process

For each release:

1. **Deploy to blue (inactive)**
   ```bash
   helm upgrade --install docflow-blue deploy/helm/docflow \
     --namespace docflow-prod \
     --values deploy/helm/docflow/values-prod.yaml \
     --set blueGreen.enabled=true \
     --set blueGreen.activeColor=blue \
     --set api.image.tag=NEW_VERSION
   ```

2. **Run smoke tests on blue**
   ```bash
   kubectl run smoke-test --rm -it --restart=Never \
     --namespace docflow-prod \
     -- curl http://docflow-api-blue/health
   ```

3. **Switch traffic to blue**
   ```bash
   kubectl patch service docflow-api \
     --namespace docflow-prod \
     -p '{"spec":{"selector":{"docflow.io/color":"blue"}}}'
   ```

4. **Rollback if needed**
   ```bash
   kubectl patch service docflow-api \
     --namespace docflow-prod \
     -p '{"spec":{"selector":{"docflow.io/color":"green"}}}'
   ```

### 4.7 Production Monitoring

- [ ] **Install Prometheus + Grafana**
  ```bash
  helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
  
  helm install prometheus prometheus-community/kube-prometheus-stack \
    --namespace monitoring \
    --create-namespace \
    --set grafana.adminPassword=YOUR_SECURE_PASSWORD
  ```

- [ ] **Access Grafana**
  ```bash
  kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80
  # Open http://localhost:3000
  # Login: admin / YOUR_SECURE_PASSWORD
  ```

- [ ] **Import DocFlow dashboards**
  - Grafana → Import → Upload JSON
  - Use dashboards from `deploy/monitoring/`

### 4.8 Production Alerts

- [ ] **Configure PagerDuty/Slack integration**
  - Grafana → Alerting → Contact Points
  - Add your notification channels

- [ ] **Enable critical alerts**
  - Pod crash loops
  - High error rates (>1%)
  - High latency (p99 > 1s)
  - Database connection failures
  - Disk space warnings

**✅ Phase 4 Complete when:** Production is running with blue/green deployments and monitoring.

---

## Phase 5: Open Source Preparation

**Goal:** Prepare DocFlow for public release on GitHub.

### 5.1 Content Scrubbing

- [ ] **Run scrub script in dry-run mode**
  ```bash
  cd /Users/ben/Projects/UT_Computational_NE/Neutron_OS/docs/_tools/docflow
  python scripts/scrub_for_oss.py . 
  # Review all proposed changes
  ```

- [ ] **Apply scrubbing**
  ```bash
  python scripts/scrub_for_oss.py . --apply
  ```

- [ ] **Manual review**
  - Check `examples/` directory
  - Review all documentation
  - Check for hardcoded paths/names
  - Review commit history for sensitive data

### 5.2 License and Legal

- [ ] **Confirm license with UT**
  - Contact UT Technology Transfer
  - Confirm Apache 2.0 is acceptable
  - Check for any IP restrictions

- [ ] **Add LICENSE file**
  ```bash
  # Already created, verify it exists
  cat LICENSE
  ```

- [ ] **Add copyright headers to source files**
  ```bash
  # Add to each .py file:
  # Copyright 2026 Neutron OS Contributors
  # SPDX-License-Identifier: Apache-2.0
  ```

### 5.3 GitHub Setup

- [ ] **Create GitHub organization**
  - Go to https://github.com/organizations/new
  - Organization name: `neutron-os`
  - Set visibility preferences

- [ ] **Create repository**
  - https://github.com/new
  - Repository name: `docflow`
  - Set to Public
  - Add description
  - Don't initialize with README (we'll push existing)

- [ ] **Push to GitHub**
  ```bash
  git remote add github git@github.com:neutron-os/docflow.git
  git push github main
  ```

### 5.4 GitHub Actions

- [ ] **Create GitHub Actions workflow**
  The file `.github/workflows/ci.yml` is already created.

- [ ] **Add GitHub secrets**
  - Repository → Settings → Secrets
  - Add: `PYPI_API_TOKEN` (for PyPI publishing)

- [ ] **Enable GitHub Container Registry**
  - Repository → Settings → Actions → General
  - Enable "Read and write permissions" for workflows

### 5.5 Package Publishing Setup

- [ ] **Reserve PyPI package name**
  - Go to https://pypi.org/
  - Create account if needed
  - Check that `docflow` name is available (or choose alternative)

- [ ] **Set up trusted publishing**
  - PyPI → Your Account → Publishing
  - Add GitHub publisher for `neutron-os/docflow`

- [ ] **Reserve VS Code extension name**
  - Go to https://marketplace.visualstudio.com/
  - Create publisher: `neutron-os`
  - Reserve name: `docflow`

### 5.6 Documentation for Public

- [ ] **Update README.md for public**
  - Remove internal references
  - Add installation instructions
  - Add contribution guidelines
  - Add badges (CI, coverage, PyPI version)

- [ ] **Create CONTRIBUTING.md**
  - How to set up development environment
  - How to run tests
  - PR process
  - Code style guidelines

- [ ] **Create SECURITY.md**
  - Security policy
  - How to report vulnerabilities
  - Supported versions

### 5.7 First Public Release

- [ ] **Create release tag**
  ```bash
  git tag -a v0.1.0 -m "Initial public release"
  git push github v0.1.0
  ```

- [ ] **GitHub release**
  - GitHub → Releases → Create Release
  - Choose tag: v0.1.0
  - Write release notes
  - Publish

- [ ] **Announce**
  - Internal team notification
  - Social media (if appropriate)
  - Relevant communities

**✅ Phase 5 Complete when:** Code is public on GitHub, package available on PyPI.

---

## Quick Reference Commands

### Local Development
```bash
./scripts/local-dev.sh start    # Start local cluster
./scripts/local-dev.sh stop     # Stop cluster
./scripts/local-dev.sh status   # Check status
./scripts/local-dev.sh logs api # View logs
./scripts/local-dev.sh clean    # Delete everything
```

### Staging
```bash
# Deploy
helm upgrade --install docflow deploy/helm/docflow \
  --namespace docflow-stage \
  --values deploy/helm/docflow/values-stage.yaml

# Check status
kubectl get pods -n docflow-stage
kubectl logs -f deploy/docflow-api -n docflow-stage
```

### Production
```bash
# Blue/green switch
kubectl patch service docflow-api \
  -n docflow-prod \
  -p '{"spec":{"selector":{"docflow.io/color":"blue"}}}'

# Rollback
kubectl patch service docflow-api \
  -n docflow-prod \
  -p '{"spec":{"selector":{"docflow.io/color":"green"}}}'
```

### Terraform
```bash
cd deploy/terraform/environments/stage  # or prod
terraform init
terraform plan -out=plan.tfplan
terraform apply plan.tfplan
terraform destroy  # DANGER: destroys everything
```

---

## Troubleshooting

### Local cluster won't start
```bash
# Reset Docker
docker system prune -a
# Delete old cluster
k3d cluster delete docflow-local
# Try again
./scripts/local-dev.sh start
```

### GitLab pipeline fails
- Check runner availability
- Verify CI variables are set
- Check Docker image builds locally first

### Terraform errors
```bash
# Refresh state
terraform refresh
# Check state
terraform state list
# Import existing resource
terraform import aws_vpc.main vpc-xxx
```

### Pods not starting
```bash
# Check events
kubectl describe pod POD_NAME -n docflow
# Check logs
kubectl logs POD_NAME -n docflow --previous
# Check resources
kubectl top nodes
kubectl top pods -n docflow
```

---

## Cost Estimates (AWS)

| Component | Stage (Monthly) | Prod (Monthly) |
|-----------|-----------------|----------------|
| EKS Cluster | $73 | $73 |
| EC2 (t3.medium x2) | ~$60 | ~$180 (m6i.large x3) |
| RDS (db.t3.medium) | ~$50 | ~$200 (db.r6g.large Multi-AZ) |
| ElastiCache | ~$15 | ~$50 |
| Load Balancer | ~$20 | ~$20 |
| Data Transfer | ~$10 | ~$50 |
| **Total** | **~$230/mo** | **~$575/mo** |

*Estimates vary by region and usage.*

---

## Next Steps After Production

1. **Performance tuning** - Load testing, query optimization
2. **Security hardening** - WAF, VPC endpoints, encryption at rest
3. **Disaster recovery** - Cross-region backup, RTO/RPO planning
4. **Cost optimization** - Reserved instances, spot instances, right-sizing
5. **Feature development** - IDE plugins, mobile app, etc.
