# DocFlow Production Deployment Guide

## 🚀 Production Readiness Checklist

### Pre-Deployment

- [ ] All tests passing (`pytest tests/ --cov=docflow --cov-report=term-missing`)
- [ ] Security audit completed (`pip-audit`)
- [ ] API keys secured in environment variables or secret manager
- [ ] Database backups configured
- [ ] Monitoring and alerting set up
- [ ] Load testing completed for expected document volume
- [ ] Disaster recovery plan documented
- [ ] Team trained on system usage

### Security Hardening

#### 1. API Key Management

```bash
# Use environment-specific .env files
.env.development
.env.staging  
.env.production

# Never commit .env files
echo ".env*" >> .gitignore

# Use secret manager for production
# Azure Key Vault example:
az keyvault secret set --vault-name docflow-kv --name ANTHROPIC-API-KEY --value $ANTHROPIC_API_KEY
```

#### 2. Database Security

```python
# production_config.py
import os
from cryptography.fernet import Fernet

# Encrypt sensitive data in database
ENCRYPTION_KEY = os.environ.get('DOCFLOW_ENCRYPTION_KEY')
if not ENCRYPTION_KEY:
    raise ValueError("DOCFLOW_ENCRYPTION_KEY must be set in production")

cipher_suite = Fernet(ENCRYPTION_KEY.encode())

# Use connection pooling
DATABASE_CONFIG = {
    'pool_size': 20,
    'max_overflow': 30,
    'pool_timeout': 30,
    'pool_recycle': 3600,
    'echo': False  # Never True in production
}
```

#### 3. Rate Limiting

```python
# rate_limiter.py
from functools import wraps
import time
from collections import defaultdict
from datetime import datetime, timedelta

class RateLimiter:
    def __init__(self, max_calls: int, period: timedelta):
        self.max_calls = max_calls
        self.period = period
        self.calls = defaultdict(list)
    
    def is_allowed(self, key: str) -> bool:
        now = datetime.now()
        # Clean old calls
        self.calls[key] = [
            call_time for call_time in self.calls[key]
            if now - call_time < self.period
        ]
        
        if len(self.calls[key]) < self.max_calls:
            self.calls[key].append(now)
            return True
        return False

# Apply to API calls
api_limiter = RateLimiter(max_calls=100, period=timedelta(minutes=1))
onedrive_limiter = RateLimiter(max_calls=1000, period=timedelta(hours=1))
llm_limiter = RateLimiter(max_calls=500, period=timedelta(hours=1))
```

### Error Handling & Recovery

#### 1. Robust Error Handling

```python
# error_handler.py
import logging
import traceback
from typing import Optional, Dict, Any
from datetime import datetime
import json

class ProductionErrorHandler:
    def __init__(self, log_dir: str = "./logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_dir / "docflow.log"),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger("docflow")
    
    def handle_error(
        self,
        error: Exception,
        context: Dict[str, Any],
        severity: str = "ERROR",
        notify: bool = True
    ) -> Optional[Dict]:
        """
        Centralized error handling with context preservation
        """
        error_id = f"ERR-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        error_data = {
            "error_id": error_id,
            "timestamp": datetime.now().isoformat(),
            "severity": severity,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
            "context": context
        }
        
        # Log error
        self.logger.error(f"[{error_id}] {error}", extra=error_data)
        
        # Save detailed error for debugging
        error_file = self.log_dir / f"{error_id}.json"
        error_file.write_text(json.dumps(error_data, indent=2))
        
        # Send notification if critical
        if notify and severity in ["CRITICAL", "ERROR"]:
            self._send_error_notification(error_data)
        
        # Return error info for API responses
        return {
            "error_id": error_id,
            "message": "An error occurred. Reference: " + error_id
        }
    
    def _send_error_notification(self, error_data: Dict):
        """Send error notification to ops team"""
        # Implement Teams/Slack/Email notification
        pass

# Global error handler
error_handler = ProductionErrorHandler()
```

#### 2. Automatic Recovery

```python
# recovery.py
import asyncio
from typing import Callable, Any, Optional
import backoff

class RecoveryManager:
    """Automatic recovery for transient failures"""
    
    @staticmethod
    @backoff.on_exception(
        backoff.expo,
        (ConnectionError, TimeoutError),
        max_tries=3,
        max_time=60
    )
    async def retry_async(
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Retry async operations with exponential backoff"""
        return await func(*args, **kwargs)
    
    @staticmethod
    async def with_timeout(
        func: Callable,
        timeout: int,
        *args,
        **kwargs
    ) -> Optional[Any]:
        """Execute with timeout"""
        try:
            return await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            error_handler.handle_error(
                TimeoutError(f"Operation timed out after {timeout}s"),
                {"function": func.__name__, "args": args},
                severity="WARNING"
            )
            return None
    
    @staticmethod
    def circuit_breaker(
        failure_threshold: int = 5,
        recovery_timeout: int = 60
    ):
        """Circuit breaker pattern for external services"""
        def decorator(func):
            func.failures = 0
            func.last_failure = None
            func.is_open = False
            
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Check if circuit is open
                if func.is_open:
                    if (datetime.now() - func.last_failure).seconds < recovery_timeout:
                        raise Exception("Circuit breaker is open")
                    else:
                        func.is_open = False
                        func.failures = 0
                
                try:
                    result = await func(*args, **kwargs)
                    func.failures = 0
                    return result
                except Exception as e:
                    func.failures += 1
                    func.last_failure = datetime.now()
                    
                    if func.failures >= failure_threshold:
                        func.is_open = True
                        error_handler.handle_error(
                            e,
                            {"service": func.__name__, "failures": func.failures},
                            severity="CRITICAL"
                        )
                    raise
            
            return wrapper
        return decorator
```

### Performance Optimization

#### 1. Caching Strategy

```python
# cache.py
from functools import lru_cache
import redis
import pickle
from typing import Optional, Any

class CacheManager:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_client = redis.from_url(redis_url)
        self.ttl_default = 3600  # 1 hour
    
    async def get(self, key: str) -> Optional[Any]:
        """Get from cache"""
        value = self.redis_client.get(key)
        if value:
            return pickle.loads(value)
        return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ):
        """Set in cache with TTL"""
        ttl = ttl or self.ttl_default
        self.redis_client.setex(
            key,
            ttl,
            pickle.dumps(value)
        )
    
    def cache_result(self, ttl: int = 3600):
        """Decorator for caching function results"""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Create cache key
                cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
                
                # Check cache
                cached = await self.get(cache_key)
                if cached:
                    return cached
                
                # Execute and cache
                result = await func(*args, **kwargs)
                await self.set(cache_key, result, ttl)
                return result
            
            return wrapper
        return decorator

# Global cache
cache = CacheManager()
```

#### 2. Database Optimization

```python
# db_optimization.py
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool

class OptimizedDatabase:
    def __init__(self, connection_string: str):
        self.engine = create_engine(
            connection_string,
            poolclass=QueuePool,
            pool_size=20,
            max_overflow=40,
            pool_timeout=30,
            pool_recycle=3600,
            pool_pre_ping=True,  # Verify connections
            echo=False
        )
        
        # Create indexes for common queries
        self._create_indexes()
    
    def _create_indexes(self):
        """Create performance indexes"""
        with self.engine.connect() as conn:
            # Document state index
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_document_state 
                ON documents(state, updated_at DESC)
            """))
            
            # Review status index
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_review_status 
                ON reviews(status, deadline)
            """))
            
            # Link tracking index
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_links 
                ON document_links(source_id, target_id)
            """))
            
            conn.commit()
    
    async def vacuum_database(self):
        """Periodic maintenance"""
        with self.engine.connect() as conn:
            conn.execute(text("VACUUM"))
            conn.execute(text("ANALYZE"))
```

### Monitoring & Observability

#### 1. Metrics Collection

```python
# metrics.py
from prometheus_client import Counter, Histogram, Gauge, start_http_server
import time

# Define metrics
document_operations = Counter(
    'docflow_document_operations_total',
    'Total document operations',
    ['operation', 'state']
)

operation_duration = Histogram(
    'docflow_operation_duration_seconds',
    'Operation duration',
    ['operation']
)

active_reviews = Gauge(
    'docflow_active_reviews',
    'Number of active reviews'
)

api_errors = Counter(
    'docflow_api_errors_total',
    'Total API errors',
    ['service', 'error_type']
)

class MetricsCollector:
    @staticmethod
    def track_operation(operation: str):
        """Decorator to track operation metrics"""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    document_operations.labels(
                        operation=operation,
                        state='success'
                    ).inc()
                    return result
                except Exception as e:
                    document_operations.labels(
                        operation=operation,
                        state='failure'
                    ).inc()
                    raise
                finally:
                    duration = time.time() - start_time
                    operation_duration.labels(
                        operation=operation
                    ).observe(duration)
            return wrapper
        return decorator

# Start metrics server
start_http_server(8000)  # Prometheus metrics on :8000/metrics
```

#### 2. Health Checks

```python
# health.py
from typing import Dict, List
import aiohttp
from datetime import datetime

class HealthChecker:
    def __init__(self):
        self.checks = []
    
    def register_check(self, name: str, check_func):
        """Register a health check"""
        self.checks.append((name, check_func))
    
    async def run_checks(self) -> Dict:
        """Run all health checks"""
        results = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "checks": {}
        }
        
        for name, check_func in self.checks:
            try:
                result = await check_func()
                results["checks"][name] = {
                    "status": "healthy" if result else "unhealthy",
                    "details": result
                }
            except Exception as e:
                results["checks"][name] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
                results["status"] = "unhealthy"
        
        return results
    
    async def check_database(self) -> bool:
        """Check database connectivity"""
        try:
            # Execute simple query
            # conn.execute("SELECT 1")
            return True
        except:
            return False
    
    async def check_storage(self) -> bool:
        """Check storage provider"""
        try:
            # List documents with limit 1
            # await storage.list_documents(limit=1)
            return True
        except:
            return False
    
    async def check_llm(self) -> bool:
        """Check LLM service"""
        try:
            # Send test prompt
            # await llm.test_connection()
            return True
        except:
            return False

# Global health checker
health = HealthChecker()
health.register_check("database", health.check_database)
health.register_check("storage", health.check_storage)
health.register_check("llm", health.check_llm)
```

### Deployment Configuration

#### 1. Docker Deployment

```dockerfile
# Dockerfile
FROM python:3.9-slim

# Security: Run as non-root user
RUN useradd -m -u 1000 docflow && \
    mkdir /app && \
    chown docflow:docflow /app

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    graphviz \
    plantuml \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY --chown=docflow:docflow . .

# Switch to non-root user
USER docflow

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8080/health')"

# Run application
CMD ["python", "-m", "docflow.daemon", "--production"]
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  docflow:
    build: .
    container_name: docflow
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - AZURE_TENANT_ID=${AZURE_TENANT_ID}
      - AZURE_CLIENT_ID=${AZURE_CLIENT_ID}
      - AZURE_CLIENT_SECRET=${AZURE_CLIENT_SECRET}
      - REDIS_URL=redis://redis:6379
      - DATABASE_URL=postgresql://docflow:${DB_PASSWORD}@postgres:5432/docflow
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    ports:
      - "8080:8080"  # API
      - "8000:8000"  # Metrics
    depends_on:
      - redis
      - postgres
    restart: unless-stopped
    networks:
      - docflow-network

  redis:
    image: redis:7-alpine
    container_name: docflow-redis
    volumes:
      - redis-data:/data
    networks:
      - docflow-network
    restart: unless-stopped

  postgres:
    image: postgres:15
    container_name: docflow-db
    environment:
      - POSTGRES_DB=docflow
      - POSTGRES_USER=docflow
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    networks:
      - docflow-network
    restart: unless-stopped

  prometheus:
    image: prom/prometheus
    container_name: docflow-prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus
    ports:
      - "9090:9090"
    networks:
      - docflow-network
    restart: unless-stopped

  grafana:
    image: grafana/grafana
    container_name: docflow-grafana
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
    volumes:
      - grafana-data:/var/lib/grafana
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards
    ports:
      - "3000:3000"
    networks:
      - docflow-network
    restart: unless-stopped

volumes:
  redis-data:
  postgres-data:
  prometheus-data:
  grafana-data:

networks:
  docflow-network:
    driver: bridge
```

#### 2. Kubernetes Deployment

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: docflow
  labels:
    app: docflow
spec:
  replicas: 3
  selector:
    matchLabels:
      app: docflow
  template:
    metadata:
      labels:
        app: docflow
    spec:
      containers:
      - name: docflow
        image: docflow:latest
        ports:
        - containerPort: 8080
          name: api
        - containerPort: 8000
          name: metrics
        env:
        - name: ANTHROPIC_API_KEY
          valueFrom:
            secretKeyRef:
              name: docflow-secrets
              key: anthropic-api-key
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: docflow-secrets
              key: database-url
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: docflow-service
spec:
  selector:
    app: docflow
  ports:
    - port: 80
      targetPort: 8080
      name: api
    - port: 8000
      targetPort: 8000
      name: metrics
  type: LoadBalancer
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: docflow-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: docflow
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### Backup & Disaster Recovery

#### 1. Automated Backups

```python
# backup.py
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
import boto3

class BackupManager:
    def __init__(self, config: Dict):
        self.config = config
        self.backup_dir = Path(config.get("backup_dir", "./backups"))
        self.backup_dir.mkdir(exist_ok=True)
        
        # S3 for offsite backups
        self.s3_client = boto3.client('s3')
        self.s3_bucket = config.get("s3_bucket", "docflow-backups")
    
    async def backup_database(self) -> str:
        """Backup SQLite database"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"docflow_db_{timestamp}.sqlite"
        
        # Copy database file (with proper locking)
        shutil.copy2(self.config["state_db_path"], backup_file)
        
        # Compress
        compressed = f"{backup_file}.gz"
        subprocess.run(["gzip", str(backup_file)])
        
        # Upload to S3
        await self.upload_to_s3(compressed, f"database/{compressed.name}")
        
        return compressed
    
    async def backup_documents(self) -> str:
        """Backup document repository"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"documents_{timestamp}.tar.gz"
        
        # Create tarball
        subprocess.run([
            "tar", "-czf", str(backup_file),
            "-C", str(self.config["repository_root"]),
            "."
        ])
        
        # Upload to S3
        await self.upload_to_s3(backup_file, f"documents/{backup_file.name}")
        
        return backup_file
    
    async def upload_to_s3(self, file_path: Path, s3_key: str):
        """Upload backup to S3"""
        try:
            self.s3_client.upload_file(
                str(file_path),
                self.s3_bucket,
                s3_key,
                ExtraArgs={
                    'ServerSideEncryption': 'AES256',
                    'StorageClass': 'GLACIER_IR'  # Cost-effective storage
                }
            )
        except Exception as e:
            error_handler.handle_error(
                e,
                {"file": str(file_path), "s3_key": s3_key},
                severity="CRITICAL"
            )
    
    async def restore_from_backup(self, backup_date: str):
        """Restore from backup"""
        # Download from S3
        # Decompress
        # Restore database
        # Restore documents
        pass
    
    def cleanup_old_backups(self, retention_days: int = 30):
        """Remove old backups"""
        cutoff = datetime.now().timestamp() - (retention_days * 86400)
        for backup in self.backup_dir.glob("*.gz"):
            if backup.stat().st_mtime < cutoff:
                backup.unlink()
```

#### 2. Disaster Recovery Plan

```yaml
# disaster_recovery.yaml
disaster_recovery_plan:
  rto: 4 hours  # Recovery Time Objective
  rpo: 1 hour   # Recovery Point Objective
  
  backup_schedule:
    database:
      frequency: hourly
      retention: 30 days
    documents:
      frequency: daily
      retention: 90 days
    configuration:
      frequency: on_change
      retention: indefinite
  
  recovery_procedures:
    1_assess:
      - Identify failure scope
      - Check monitoring dashboards
      - Review error logs
    
    2_communicate:
      - Notify incident team
      - Update status page
      - Inform stakeholders
    
    3_restore:
      - Switch to DR environment
      - Restore from latest backup
      - Verify data integrity
      - Run health checks
    
    4_validate:
      - Test critical workflows
      - Verify document access
      - Check integrations
    
    5_cutover:
      - Update DNS if needed
      - Redirect traffic
      - Monitor closely
  
  test_schedule:
    - Quarterly DR drills
    - Monthly backup restoration tests
    - Weekly health check validation
```

### Production Checklist

#### Pre-Production

```bash
#!/bin/bash
# pre_production_check.sh

echo "DocFlow Pre-Production Checklist"
echo "================================="

# 1. Run all tests
echo "[ ] Running tests..."
pytest tests/ --cov=docflow --cov-report=term-missing
if [ $? -ne 0 ]; then
    echo "[X] Tests failed. Fix before deploying."
    exit 1
fi

# 2. Security scan
echo "[ ] Running security scan..."
pip-audit
bandit -r docflow/

# 3. Check environment variables
echo "[ ] Checking environment variables..."
required_vars=(
    "ANTHROPIC_API_KEY"
    "AZURE_TENANT_ID"
    "AZURE_CLIENT_ID"
    "AZURE_CLIENT_SECRET"
    "DATABASE_URL"
)

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "[X] Missing required environment variable: $var"
        exit 1
    fi
done

# 4. Database migrations
echo "[ ] Checking database..."
python -m docflow.db migrate

# 5. Build Docker image
echo "[ ] Building Docker image..."
docker build -t docflow:latest .

# 6. Run integration tests
echo "[ ] Running integration tests..."
docker-compose -f docker-compose.test.yml up --abort-on-container-exit

echo ""
echo "✅ All checks passed! Ready for production deployment."
```

#### Post-Deployment Verification

```python
# verify_deployment.py
import asyncio
import aiohttp
from typing import List, Dict

async def verify_deployment(base_url: str) -> Dict:
    """Verify production deployment"""
    results = {
        "status": "unknown",
        "checks": {},
        "timestamp": datetime.now().isoformat()
    }
    
    async with aiohttp.ClientSession() as session:
        # 1. Health check
        try:
            async with session.get(f"{base_url}/health") as resp:
                if resp.status == 200:
                    results["checks"]["health"] = "passed"
                else:
                    results["checks"]["health"] = f"failed: {resp.status}"
        except Exception as e:
            results["checks"]["health"] = f"error: {e}"
        
        # 2. API endpoints
        endpoints = ["/api/documents", "/api/reviews", "/api/status"]
        for endpoint in endpoints:
            try:
                async with session.get(f"{base_url}{endpoint}") as resp:
                    results["checks"][endpoint] = resp.status == 200
            except:
                results["checks"][endpoint] = False
        
        # 3. Can create document
        try:
            test_doc = {
                "title": "Deployment Test",
                "content": "Test document",
                "state": "draft"
            }
            async with session.post(
                f"{base_url}/api/documents",
                json=test_doc
            ) as resp:
                results["checks"]["create_document"] = resp.status == 201
        except:
            results["checks"]["create_document"] = False
    
    # Determine overall status
    if all(v in [True, "passed"] for v in results["checks"].values()):
        results["status"] = "healthy"
    else:
        results["status"] = "unhealthy"
    
    return results

if __name__ == "__main__":
    result = asyncio.run(verify_deployment("https://docflow.yourorg.com"))
    print(json.dumps(result, indent=2))
```

## 📊 Monitoring Dashboard Configuration

### Grafana Dashboard

```json
{
  "dashboard": {
    "title": "DocFlow Production Metrics",
    "panels": [
      {
        "title": "Document Operations",
        "targets": [
          {
            "expr": "rate(docflow_document_operations_total[5m])"
          }
        ]
      },
      {
        "title": "Active Reviews",
        "targets": [
          {
            "expr": "docflow_active_reviews"
          }
        ]
      },
      {
        "title": "API Error Rate",
        "targets": [
          {
            "expr": "rate(docflow_api_errors_total[5m])"
          }
        ]
      },
      {
        "title": "Operation Duration (p95)",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(docflow_operation_duration_seconds_bucket[5m]))"
          }
        ]
      }
    ]
  }
}
```

## 🚨 Alerts Configuration

```yaml
# alerts.yaml
groups:
  - name: docflow_alerts
    rules:
      - alert: HighErrorRate
        expr: rate(docflow_api_errors_total[5m]) > 0.1
        for: 5m
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value }} errors/sec"
      
      - alert: ReviewBacklog
        expr: docflow_active_reviews > 50
        for: 10m
        annotations:
          summary: "Large review backlog"
          description: "{{ $value }} reviews pending"
      
      - alert: DatabaseConnectionFailure
        expr: up{job="docflow-db"} == 0
        for: 1m
        annotations:
          summary: "Database connection lost"
          severity: critical
      
      - alert: LowDiskSpace
        expr: node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"} < 0.1
        for: 5m
        annotations:
          summary: "Low disk space"
          description: "Less than 10% disk space remaining"
```

## 🔐 Security Best Practices

1. **Never commit secrets** - Use environment variables or secret managers
2. **Rotate API keys** quarterly
3. **Use HTTPS everywhere** - Enforce TLS 1.2+
4. **Implement RBAC** - Role-based access control for users
5. **Audit logs** - Keep audit trail of all operations
6. **Regular updates** - Keep dependencies updated
7. **Vulnerability scanning** - Run security scans in CI/CD
8. **Backup encryption** - Encrypt backups at rest and in transit
9. **Network segmentation** - Isolate DocFlow components
10. **Incident response plan** - Have procedures ready

## 📈 Performance Tuning

### Database
- Use connection pooling
- Create appropriate indexes
- Regular VACUUM and ANALYZE
- Consider read replicas for scaling

### Caching
- Cache frequently accessed documents
- Use Redis for session storage
- CDN for static assets

### Async Operations
- Use background workers for heavy tasks
- Implement job queues (Celery, RQ)
- Batch operations where possible

### API Optimization
- Implement pagination
- Use compression (gzip)
- Rate limiting per user/IP
- Request/response caching

## 🎯 Success Metrics

Track these KPIs post-deployment:

- **Availability**: >99.9% uptime
- **Performance**: <200ms p95 latency
- **Error Rate**: <0.1% of requests
- **Review Turnaround**: <48 hours average
- **Document Publishing**: <5 minutes end-to-end
- **User Satisfaction**: >4.5/5 rating

---

**Production deployment typically takes 2-4 hours including verification. Plan for a maintenance window and have rollback procedures ready.**