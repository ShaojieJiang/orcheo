"""Workspace models providing multi-tenant collaboration features."""

from __future__ import annotations
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4


@dataclass(slots=True)
class WorkspaceMember:
    """Represents a member within a workspace."""

    user_id: UUID
    email: str
    roles: set[str] = field(default_factory=set)

    def assign_role(self, role: str) -> None:
        """Assign a normalised role to the member."""
        self.roles.add(role.lower())

    def revoke_role(self, role: str) -> None:
        """Remove a role from the member if present."""
        self.roles.discard(role.lower())


@dataclass(slots=True)
class Workspace:
    """Team workspace supporting membership and audit metadata."""

    name: str
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    members: dict[UUID, WorkspaceMember] = field(default_factory=dict)
    audit_log: list[str] = field(default_factory=list)

    def add_member(self, member: WorkspaceMember) -> None:
        """Add or replace a workspace member and log the action."""
        self.members[member.user_id] = member
        self._log(f"member_added:{member.email}")

    def remove_member(self, user_id: UUID) -> None:
        """Remove a member if present and record the removal."""
        if user_id in self.members:
            email = self.members[user_id].email
            del self.members[user_id]
            self._log(f"member_removed:{email}")

    def list_members(self) -> Iterable[WorkspaceMember]:
        """Return all current workspace members."""
        return self.members.values()

    def _log(self, message: str) -> None:
        """Append a timestamped audit message."""
        timestamp = datetime.now(tz=UTC).isoformat()
        self.audit_log.append(f"{timestamp}:{message}")


__all__ = ["Workspace", "WorkspaceMember"]
