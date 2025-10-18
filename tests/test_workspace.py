from uuid import uuid4

from orcheo.models.workspace import Workspace, WorkspaceMember


def test_workspace_membership_tracking() -> None:
    workspace = Workspace(name="Team Alpha")
    member_id = uuid4()
    member = WorkspaceMember(user_id=member_id, email="user@example.com")
    member.assign_role("Admin")
    workspace.add_member(member)

    members = list(workspace.list_members())
    assert members[0].email == "user@example.com"
    assert "admin" in members[0].roles
    assert any(
        entry.endswith("member_added:user@example.com") for entry in workspace.audit_log
    )

    workspace.remove_member(member_id)
    assert list(workspace.list_members()) == []
    assert any(
        entry.endswith("member_removed:user@example.com")
        for entry in workspace.audit_log
    )
