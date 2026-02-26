"""SQLite-based persistence for DocFlow state."""

import logging
import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional

from .state import WorkflowState, DocumentState, ReviewPeriod

logger = logging.getLogger(__name__)


class StatePersistence:
    """Persist DocFlow state to SQLite database."""
    
    SCHEMA_VERSION = 1
    
    def __init__(self, db_path: Path = None):
        """Initialize persistence layer.
        
        Args:
            db_path: Path to SQLite database (default: .docflow/state.db)
        """
        self.db_path = db_path or Path.cwd() / ".docflow" / "state.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    def _ensure_schema(self) -> None:
        """Create tables if they don't exist."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Check if schema exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
            )
            if cursor.fetchone():
                return  # Schema already exists
            
            # Create schema
            cursor.execute("""
                CREATE TABLE schema_version (
                    version INTEGER,
                    created_at TEXT
                )
            """)
            
            cursor.execute("""
                CREATE TABLE workflow_state (
                    id INTEGER PRIMARY KEY,
                    current_branch TEXT,
                    current_commit TEXT,
                    git_root TEXT,
                    last_poll TEXT,
                    last_poll_error TEXT,
                    state_json TEXT,
                    updated_at TEXT
                )
            """)
            
            cursor.execute("""
                CREATE TABLE document_state (
                    doc_id TEXT PRIMARY KEY,
                    state_json TEXT,
                    updated_at TEXT
                )
            """)
            
            cursor.execute("""
                CREATE TABLE mutations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    doc_id TEXT,
                    mutation_type TEXT,
                    old_value TEXT,
                    new_value TEXT,
                    actor TEXT,
                    reason TEXT
                )
            """)
            
            cursor.execute("""
                CREATE TABLE actions (
                    action_id TEXT PRIMARY KEY,
                    doc_id TEXT,
                    action_type TEXT,
                    status TEXT,
                    proposed_at TEXT,
                    approved_at TEXT,
                    rejected_at TEXT,
                    rejection_reason TEXT,
                    data_json TEXT
                )
            """)
            
            # Insert version
            cursor.execute(
                "INSERT INTO schema_version (version, created_at) VALUES (?, ?)",
                (self.SCHEMA_VERSION, datetime.now().isoformat())
            )
            
            conn.commit()
            logger.info(f"Created DocFlow state schema at {self.db_path}")
        
        except Exception as e:
            logger.error(f"Failed to create schema: {e}")
            raise
        
        finally:
            conn.close()
    
    def save_workflow_state(self, state: WorkflowState) -> bool:
        """Save workflow state to database.
        
        Args:
            state: WorkflowState to save
        
        Returns:
            True if successful
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            state_json = self._serialize_workflow_state(state)
            
            cursor.execute("""
                INSERT OR REPLACE INTO workflow_state 
                (current_branch, current_commit, git_root, last_poll, last_poll_error, 
                 state_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                state.current_branch,
                state.current_commit,
                str(state.git_root),
                state.last_poll.isoformat() if state.last_poll else None,
                state.last_poll_error,
                state_json,
                datetime.now().isoformat()
            ))
            
            conn.commit()
            logger.debug("Saved workflow state")
            return True
        
        except Exception as e:
            logger.error(f"Failed to save workflow state: {e}")
            return False
        
        finally:
            conn.close()
    
    def load_workflow_state(self) -> Optional[WorkflowState]:
        """Load workflow state from database.
        
        Returns:
            WorkflowState or None if not found
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT state_json, current_branch, current_commit, git_root, last_poll
                FROM workflow_state
                ORDER BY updated_at DESC
                LIMIT 1
            """)
            
            row = cursor.fetchone()
            if not row:
                return None
            
            return self._deserialize_workflow_state(dict(row))
        
        except Exception as e:
            logger.error(f"Failed to load workflow state: {e}")
            return None
        
        finally:
            conn.close()
    
    def save_document_state(self, doc_state: DocumentState) -> bool:
        """Save document state to database.
        
        Args:
            doc_state: DocumentState to save
        
        Returns:
            True if successful
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            state_json = self._serialize_document_state(doc_state)
            
            cursor.execute("""
                INSERT OR REPLACE INTO document_state 
                (doc_id, state_json, updated_at)
                VALUES (?, ?, ?)
            """, (
                doc_state.doc_id,
                state_json,
                datetime.now().isoformat()
            ))
            
            conn.commit()
            logger.debug(f"Saved state for {doc_state.doc_id}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to save document state: {e}")
            return False
        
        finally:
            conn.close()
    
    def load_document_state(self, doc_id: str) -> Optional[DocumentState]:
        """Load document state from database.
        
        Args:
            doc_id: Document ID
        
        Returns:
            DocumentState or None if not found
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT state_json FROM document_state WHERE doc_id = ?
            """, (doc_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            return self._deserialize_document_state(json.loads(row[0]))
        
        except Exception as e:
            logger.error(f"Failed to load document state: {e}")
            return None
        
        finally:
            conn.close()
    
    def record_mutation(self, doc_id: str, mutation_type: str, old_value: str,
                       new_value: str, actor: str = "system", reason: str = None) -> bool:
        """Record a state mutation for audit trail.
        
        Args:
            doc_id: Document ID
            mutation_type: Type of mutation (e.g., "publish", "comment_added", "promoted")
            old_value: Previous value (JSON string)
            new_value: New value (JSON string)
            actor: Who made the change
            reason: Why the change was made
        
        Returns:
            True if successful
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO mutations 
                (timestamp, doc_id, mutation_type, old_value, new_value, actor, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                doc_id,
                mutation_type,
                old_value,
                new_value,
                actor,
                reason
            ))
            
            conn.commit()
            return True
        
        except Exception as e:
            logger.error(f"Failed to record mutation: {e}")
            return False
        
        finally:
            conn.close()
    
    def get_mutations(self, doc_id: str = None, limit: int = 100) -> list[dict]:
        """Get mutation history.
        
        Args:
            doc_id: Optional filter by document
            limit: Max results
        
        Returns:
            List of mutation records
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            if doc_id:
                cursor.execute("""
                    SELECT * FROM mutations 
                    WHERE doc_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (doc_id, limit))
            else:
                cursor.execute("""
                    SELECT * FROM mutations 
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,))
            
            return [dict(row) for row in cursor.fetchall()]
        
        except Exception as e:
            logger.error(f"Failed to retrieve mutations: {e}")
            return []
        
        finally:
            conn.close()
    
    def propose_action(self, action_id: str, doc_id: str, action_type: str,
                      data: dict) -> bool:
        """Record a proposed action (pending approval).
        
        Args:
            action_id: Unique action ID
            doc_id: Document ID
            action_type: Type of action (e.g., "update_source", "promote")
            data: Action data (JSON-serializable dict)
        
        Returns:
            True if successful
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO actions
                (action_id, doc_id, action_type, status, proposed_at, data_json)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                action_id,
                doc_id,
                action_type,
                "pending",
                datetime.now().isoformat(),
                json.dumps(data)
            ))
            
            conn.commit()
            return True
        
        except Exception as e:
            logger.error(f"Failed to propose action: {e}")
            return False
        
        finally:
            conn.close()
    
    def approve_action(self, action_id: str) -> bool:
        """Approve a proposed action.
        
        Args:
            action_id: Action ID
        
        Returns:
            True if successful
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE actions
                SET status = 'approved', approved_at = ?
                WHERE action_id = ?
            """, (datetime.now().isoformat(), action_id))
            
            conn.commit()
            return True
        
        except Exception as e:
            logger.error(f"Failed to approve action: {e}")
            return False
        
        finally:
            conn.close()
    
    def _serialize_workflow_state(self, state: WorkflowState) -> str:
        """Serialize WorkflowState to JSON."""
        data = {
            "documents": {
                doc_id: self._serialize_document_state_dict(doc_state)
                for doc_id, doc_state in state.documents.items()
            },
            "pending_actions": state.pending_actions,
        }
        return json.dumps(data)
    
    def _deserialize_workflow_state(self, data: dict) -> WorkflowState:
        """Deserialize WorkflowState from database row."""
        state = WorkflowState(
            current_branch=data.get("current_branch", ""),
            current_commit=data.get("current_commit", ""),
        )
        
        if data.get("last_poll"):
            state.last_poll = datetime.fromisoformat(data["last_poll"])
        
        # TODO: Deserialize documents
        return state
    
    def _serialize_document_state_dict(self, doc_state: DocumentState) -> dict:
        """Convert DocumentState to serializable dict."""
        # This is a simplified version - full implementation would handle
        # all nested objects properly
        return {
            "doc_id": doc_state.doc_id,
            "source_path": doc_state.source_path,
            "approval_required": doc_state.approval_required,
            "auto_republish": doc_state.auto_republish,
        }
    
    def _serialize_document_state(self, doc_state: DocumentState) -> str:
        """Serialize DocumentState to JSON."""
        data = self._serialize_document_state_dict(doc_state)
        return json.dumps(data)
    
    def _deserialize_document_state(self, data: dict) -> Optional[DocumentState]:
        """Deserialize DocumentState from dict."""
        try:
            state = DocumentState(
                doc_id=data.get("doc_id", ""),
                source_path=data.get("source_path", ""),
            )
            state.approval_required = data.get("approval_required", True)
            state.auto_republish = data.get("auto_republish", False)
            return state
        except Exception as e:
            logger.error(f"Failed to deserialize document state: {e}")
            return None
