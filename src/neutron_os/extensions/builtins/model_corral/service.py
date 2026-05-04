"""ModelCorralService — core business logic for the model registry.

Orchestrates validation, storage, and database operations. All CLI commands
and agent tools delegate to this service.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from axiom.infra.storage.base import StorageProvider

from .db_models import ModelLineage, ModelRegistry, ModelVersion
from .manifest import validate_model_dir


@dataclass
class AddResult:
    success: bool
    model_id: str = ""
    version: str = ""
    error: str = ""


@dataclass
class PullResult:
    success: bool
    path: str = ""
    error: str = ""


class ModelCorralService:
    """Core service for model registry operations."""

    def __init__(self, engine: Engine, storage: StorageProvider):
        self._engine = engine
        self._storage = storage

    # ------------------------------------------------------------------
    # Add (M1.5)
    # ------------------------------------------------------------------

    def add(
        self, model_dir: Path, message: str = "", coreforge_provenance: dict | None = None
    ) -> AddResult:
        """Validate, upload, and register a model from a local directory."""
        # Validate first
        validation = validate_model_dir(model_dir)
        if not validation.valid:
            return AddResult(
                success=False,
                error=f"Validation failed: {'; '.join(validation.errors)}",
            )

        data = validation.data
        model_id = data["model_id"]
        version = data["version"]

        with Session(self._engine) as session:
            # Check for duplicate version
            existing = (
                session.query(ModelVersion).filter_by(model_id=model_id, version=version).first()
            )
            if existing:
                return AddResult(
                    success=False,
                    model_id=model_id,
                    version=version,
                    error=f"Version {version} already exists for {model_id}",
                )

            # Compute checksum of all files
            checksum = self._compute_checksum(model_dir)

            # Upload files to storage
            storage_prefix = self._storage_path(data)
            for file_path in model_dir.rglob("*"):
                if file_path.is_file():
                    rel = file_path.relative_to(model_dir)
                    self._storage.upload(file_path, f"{storage_prefix}/{rel}")

            # Upsert model_registry
            model = session.get(ModelRegistry, model_id)
            if model is None:
                model = ModelRegistry(
                    model_id=model_id,
                    name=data.get("name", model_id),
                    reactor_type=data.get("reactor_type", "custom"),
                    facility=data.get("facility", ""),
                    physics_code=data.get("physics_code", ""),
                    code_version=data.get("code_version"),
                    status=data.get("status", "draft"),
                    access_tier=data.get("access_tier", "facility"),
                    description=data.get("description", ""),
                    tags=data.get("tags", []),
                    created_by=data.get("created_by", ""),
                )
                session.add(model)
            else:
                # Update mutable fields
                model.status = data.get("status", model.status)
                model.description = data.get("description", model.description)
                model.tags = data.get("tags", model.tags)

            session.flush()

            # Create version record
            ver = ModelVersion(
                model_id=model_id,
                version=version,
                storage_path=storage_prefix,
                manifest=data,
                checksum=checksum,
                created_by=data.get("created_by", ""),
                coreforge_provenance=coreforge_provenance,
            )
            session.add(ver)

            # Create lineage if parent_model specified
            parent_id = data.get("parent_model")
            if parent_id:
                rel_type = "trained_from" if data.get("rom_tier") else "derived"
                lineage = ModelLineage(
                    model_id=model_id,
                    parent_model_id=parent_id,
                    relationship_type=rel_type,
                )
                session.add(lineage)

            session.commit()

        # Trigger immediate sync to Git remote (non-blocking on failure)
        try:
            from .sync import ModelSyncAgent

            sync = ModelSyncAgent()
            if sync.enabled:
                sync.sync_model(data)
        except Exception:
            pass  # Sync failure should never block add

        return AddResult(success=True, model_id=model_id, version=version)

    # ------------------------------------------------------------------
    # List / Show / Search (M1.6)
    # ------------------------------------------------------------------

    def list_models(
        self,
        reactor_type: str | None = None,
        physics_code: str | None = None,
        status: str | None = None,
        facility: str | None = None,
    ) -> list[dict]:
        """List models with optional filters."""
        with Session(self._engine) as session:
            q = session.query(ModelRegistry)
            if reactor_type:
                q = q.filter(ModelRegistry.reactor_type == reactor_type)
            if physics_code:
                q = q.filter(ModelRegistry.physics_code == physics_code)
            if status:
                q = q.filter(ModelRegistry.status == status)
            if facility:
                q = q.filter(ModelRegistry.facility == facility)

            return [self._model_to_dict(m) for m in q.all()]

    def show(self, model_id: str) -> dict | None:
        """Get full details for a model including versions."""
        with Session(self._engine) as session:
            model = session.get(ModelRegistry, model_id)
            if model is None:
                return None

            info = self._model_to_dict(model)
            info["versions"] = [
                {
                    "version": v.version,
                    "storage_path": v.storage_path,
                    "checksum": v.checksum,
                    "created_at": str(v.created_at) if v.created_at else None,
                    "created_by": v.created_by,
                }
                for v in model.versions
            ]
            return info

    def search(self, query: str) -> list[dict]:
        """Search models by keyword (name, description, tags, model_id)."""
        query_lower = query.lower()
        with Session(self._engine) as session:
            all_models = session.query(ModelRegistry).all()
            results = []
            for m in all_models:
                searchable = " ".join(
                    filter(
                        None,
                        [
                            m.model_id,
                            m.name,
                            m.description or "",
                            m.reactor_type,
                            m.physics_code,
                            " ".join(m.tags or []),
                        ],
                    )
                ).lower()
                if query_lower in searchable:
                    results.append(self._model_to_dict(m))
            return results

    # ------------------------------------------------------------------
    # Pull (M1.7)
    # ------------------------------------------------------------------

    def pull(self, model_id: str, dest: Path, version: str | None = None) -> PullResult:
        """Download a model from the registry to a local directory."""
        with Session(self._engine) as session:
            model = session.get(ModelRegistry, model_id)
            if model is None:
                return PullResult(success=False, error=f"Model not found: {model_id}")

            # Find the version
            if version:
                ver = (
                    session.query(ModelVersion)
                    .filter_by(model_id=model_id, version=version)
                    .first()
                )
            else:
                ver = (
                    session.query(ModelVersion)
                    .filter_by(model_id=model_id)
                    .order_by(ModelVersion.id.desc())
                    .first()
                )

            if ver is None:
                return PullResult(success=False, error=f"No version found for {model_id}")

            # Download all files from storage
            prefix = ver.storage_path
            entries = self._storage.list_artifacts(prefix + "/")

            dest.mkdir(parents=True, exist_ok=True)
            for entry in entries:
                # Strip prefix to get relative path
                rel = entry.storage_id
                if rel.startswith(prefix + "/"):
                    rel = rel[len(prefix) + 1 :]
                local_path = dest / rel
                self._storage.download(entry.storage_id, local_path)

        return PullResult(success=True, path=str(dest))

    # ------------------------------------------------------------------
    # Lineage (M1.8)
    # ------------------------------------------------------------------

    def lineage(self, model_id: str) -> list[dict]:
        """Get the lineage chain for a model (parents, not children)."""
        with Session(self._engine) as session:
            entries = session.query(ModelLineage).filter_by(model_id=model_id).all()
            return [
                {
                    "model_id": e.model_id,
                    "parent_model_id": e.parent_model_id,
                    "relationship_type": e.relationship_type,
                }
                for e in entries
            ]

    # ------------------------------------------------------------------
    # Reviews
    # ------------------------------------------------------------------

    def add_review(
        self,
        model_id: str,
        reviewer: str,
        comment: str,
        version: str | None = None,
        *,
        reviews_dir: Path | None = None,
    ) -> dict:
        """Add a review comment to a model."""
        from datetime import UTC, datetime
        import secrets

        review = {
            "review_id": f"rev-{secrets.token_hex(6)}",
            "model_id": model_id,
            "version": version,
            "reviewer": reviewer,
            "comment": comment,
            "created_at": datetime.now(UTC).isoformat(),
            "status": "open",
        }

        if reviews_dir is None:
            from axiom.infra.paths import get_user_state_dir

            reviews_dir = get_user_state_dir() / "model-reviews"

        reviews_dir.mkdir(parents=True, exist_ok=True)
        reviews_file = reviews_dir / f"{model_id}.jsonl"

        from axiom.infra.state import locked_append_jsonl

        locked_append_jsonl(reviews_file, review)
        return review

    def get_reviews(
        self,
        model_id: str,
        status: str | None = None,
        *,
        reviews_dir: Path | None = None,
    ) -> list[dict]:
        """Get all reviews for a model."""
        import json

        if reviews_dir is None:
            from axiom.infra.paths import get_user_state_dir

            reviews_dir = get_user_state_dir() / "model-reviews"

        reviews_file = reviews_dir / f"{model_id}.jsonl"
        if not reviews_file.exists():
            return []

        reviews = []
        for line in reviews_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    review = json.loads(line)
                    if status and review.get("status") != status:
                        continue
                    reviews.append(review)
                except json.JSONDecodeError:
                    continue
        return reviews

    def resolve_review(
        self,
        model_id: str,
        review_id: str,
        resolution: str = "addressed",
        *,
        reviews_dir: Path | None = None,
    ) -> bool:
        """Mark a review as addressed or dismissed."""
        import json

        if reviews_dir is None:
            from axiom.infra.paths import get_user_state_dir

            reviews_dir = get_user_state_dir() / "model-reviews"

        reviews_file = reviews_dir / f"{model_id}.jsonl"
        if not reviews_file.exists():
            return False

        lines = reviews_file.read_text(encoding="utf-8").splitlines()
        updated = False
        new_lines = []
        for line in lines:
            if line.strip():
                review = json.loads(line)
                if review.get("review_id") == review_id:
                    review["status"] = resolution
                    updated = True
                new_lines.append(json.dumps(review))

        if updated:
            reviews_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        return updated

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _storage_path(data: dict) -> str:
        """Build the object storage prefix for a model version."""
        reactor = data.get("reactor_type", "unknown").lower()
        facility = data.get("facility", "unknown").lower()
        code = data.get("physics_code", "unknown").lower()
        model_id = data["model_id"]
        version = data["version"]
        return f"models/{reactor}/{facility}/{code}/{model_id}/v{version}"

    @staticmethod
    def _compute_checksum(model_dir: Path) -> str:
        """SHA-256 of all file contents in a model directory."""
        h = hashlib.sha256()
        for f in sorted(model_dir.rglob("*")):
            if f.is_file():
                h.update(f.read_bytes())
        return h.hexdigest()

    @staticmethod
    def _model_to_dict(model: ModelRegistry) -> dict:
        return {
            "model_id": model.model_id,
            "name": model.name,
            "reactor_type": model.reactor_type,
            "facility": model.facility,
            "physics_code": model.physics_code,
            "status": model.status,
            "access_tier": model.access_tier,
            "description": model.description,
            "tags": model.tags or [],
            "created_by": model.created_by,
        }
