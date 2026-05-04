"""SQLAlchemy models for Model Corral.

Tables:
- model_registry: Core model metadata (from model.yaml)
- model_versions: Version history with storage paths
- model_lineage: Parent-child relationships (fork, derived, trained_from)
- model_validations: Validation run results with metrics
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    Float,
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class ModelRegistry(Base):
    __tablename__ = "model_registry"

    model_id = Column(String(255), primary_key=True)
    name = Column(String(500), nullable=False)
    reactor_type = Column(String(50), nullable=False)
    facility = Column(String(100), nullable=False)
    physics_code = Column(String(50), nullable=False)
    code_version = Column(String(50))
    status = Column(String(20), nullable=False, default="draft")
    access_tier = Column(String(20), nullable=False, default="facility")
    description = Column(Text)
    tags = Column(JSON, default=list)
    created_by = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    versions = relationship("ModelVersion", back_populates="model", cascade="all, delete-orphan")
    lineage_children = relationship(
        "ModelLineage",
        foreign_keys="ModelLineage.model_id",
        back_populates="model",
        cascade="all, delete-orphan",
    )


class ModelVersion(Base):
    __tablename__ = "model_versions"
    __table_args__ = (UniqueConstraint("model_id", "version", name="uq_model_version"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_id = Column(String(255), ForeignKey("model_registry.model_id"), nullable=False)
    version = Column(String(50), nullable=False)
    storage_path = Column(String(1000))
    manifest = Column(JSON)
    checksum = Column(String(128))
    coreforge_provenance = Column(JSON)  # CoreForge config, builder specs, geometry hash
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    created_by = Column(String(255))

    model = relationship("ModelRegistry", back_populates="versions")
    validations = relationship(
        "ModelValidation", back_populates="model_version", cascade="all, delete-orphan"
    )


class ModelLineage(Base):
    __tablename__ = "model_lineage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_id = Column(String(255), ForeignKey("model_registry.model_id"), nullable=False)
    parent_model_id = Column(String(255), ForeignKey("model_registry.model_id"), nullable=False)
    relationship_type = Column(String(50), nullable=False)  # fork, derived, trained_from
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    model = relationship(
        "ModelRegistry", foreign_keys=[model_id], back_populates="lineage_children"
    )
    parent = relationship("ModelRegistry", foreign_keys=[parent_model_id])


class ModelValidation(Base):
    __tablename__ = "model_validations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_id = Column(String(255), ForeignKey("model_registry.model_id"), nullable=False)
    version_id = Column(Integer, ForeignKey("model_versions.id"))
    validation_dataset = Column(String(500))
    status = Column(String(20))  # unvalidated, in_progress, validated, failed
    metrics = Column(JSON)
    validated_by = Column(String(255))
    validated_at = Column(DateTime)

    model_version = relationship("ModelVersion", back_populates="validations")


class MaterialRecord(Base):
    """Persisted material composition for federation + search.

    Materials from YAML files and CoreForge are indexed here for
    full-text search, federation distribution, and audit trail.
    """

    __tablename__ = "material_records"
    __table_args__ = (UniqueConstraint("name", "data_library", name="uq_material_name_library"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, index=True)
    description = Column(Text)
    density = Column(Float, nullable=False)
    category = Column(String(50), nullable=False)
    fraction_type = Column(String(10), nullable=False, default="atom")
    temperature_k = Column(Float, default=293.6)
    source_reference = Column(String(500))  # literature reference
    data_library = Column(String(50))  # "ENDF/B-VII.1", "ENDF/B-VIII.0"
    data_library_version = Column(String(50))
    composition_hash = Column(String(128), nullable=False)  # SHA-256 of isotope data
    isotope_data = Column(JSON, nullable=False)  # [{zaid, fraction, name}, ...]
    sab = Column(String(100))  # S(alpha,beta) library

    # FAIR metadata
    license = Column(String(100))  # "CC-BY-4.0", etc.
    pid = Column(String(255))  # persistent identifier (DOI)

    # Provenance
    material_source = Column(
        String(50), nullable=False
    )  # "builtin", "yaml", "coreforge", "federation"
    facility_pack = Column(String(100))  # which facility pack, if any

    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )
