"""Unified human-in-the-loop review framework.

Provides a channel-agnostic data model and interactive CLI runner for
reviewing any kind of AI-generated output: draft documents, STT corrections,
action proposals, etc.

Architecture:
    ReviewItem / ReviewSession / ReviewSessionStore  (models.py)
    ReviewAdapter protocol + ReviewRunner            (runner.py)
    Domain-specific adapters                         (adapters/)
"""
