"""Human-in-the-loop approval gate.

Classifies actions as read-only (auto-approve) or write (require human
confirmation). For safety-adjacent nuclear facility operations, all writes
must be explicitly approved.

Optionally integrates with PermissionStore to auto-approve tools the
user has previously allowed.

Usage:
    gate = ApprovalGate()

    # Read-only → auto-approved
    action = create_action("query_docs")
    gate.submit(action)  # action.status == APPROVED

    # Write → pending human approval
    action = create_action("doc_publish", {"source": "docs/prd/foo.md"})
    gate.submit(action)  # action.status == PENDING
    gate.pending()       # [action]
    gate.approve(action.action_id)  # action.status == APPROVED

    # With permission store → auto-approve remembered tools
    from tools.agents.orchestrator.permissions import PermissionStore
    perms = PermissionStore()
    perms.allow_session("doc_publish")
    gate = ApprovalGate(permissions=perms)
    action = create_action("doc_publish")
    gate.submit(action)  # action.status == APPROVED (auto via permissions)
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from tools.agents.orchestrator.actions import (
    Action,
    ActionCategory,
    ActionStatus,
)

if TYPE_CHECKING:
    from tools.agents.orchestrator.permissions import PermissionStore


class ApprovalGate:
    """Manages the approval lifecycle for actions.

    Read-only actions are auto-approved. Write actions are held
    for human confirmation unless the PermissionStore has a rule.
    """

    def __init__(self, permissions: Optional[PermissionStore] = None):
        self._actions: dict[str, Action] = {}
        self._permissions = permissions

    def submit(self, action: Action) -> Action:
        """Submit an action for approval.

        Read-only actions are automatically approved.
        Write actions with permission memory are auto-approved.
        Other write actions are placed in pending state.

        Returns:
            The action (possibly with updated status).
        """
        self._actions[action.action_id] = action

        if action.category == ActionCategory.READ:
            action.approve()
        elif self._permissions and self._permissions.is_allowed(action.name):
            action.approve()

        return action

    def approve(self, action_id: str) -> Optional[Action]:
        """Approve a pending action."""
        action = self._actions.get(action_id)
        if action and action.status == ActionStatus.PENDING:
            action.approve()
        return action

    def reject(self, action_id: str, reason: str = "") -> Optional[Action]:
        """Reject a pending action."""
        action = self._actions.get(action_id)
        if action and action.status == ActionStatus.PENDING:
            action.reject(reason)
        return action

    def pending(self) -> list[Action]:
        """Return all actions awaiting approval."""
        return [
            a for a in self._actions.values()
            if a.status == ActionStatus.PENDING
        ]

    def get(self, action_id: str) -> Optional[Action]:
        """Look up an action by ID."""
        return self._actions.get(action_id)

    def all_actions(self) -> list[Action]:
        """Return all tracked actions."""
        return list(self._actions.values())
