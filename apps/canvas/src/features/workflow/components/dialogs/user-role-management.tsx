import React, { useMemo, useState } from "react";
import { Input } from "@/design-system/ui/input";
import { Search } from "lucide-react";
import { cn } from "@/lib/utils";
import InviteUserDialog from "@/features/workflow/components/dialogs/user-role-management/invite-user-dialog";
import UserRoleTable from "@/features/workflow/components/dialogs/user-role-management/user-role-table";
import type {
  UserRoleManagementProps,
  User,
} from "@/features/workflow/components/dialogs/user-role-management/user-role-types";

export default function UserRoleManagement({
  users = [],
  onInviteUser,
  onUpdateUserRole,
  onRemoveUser,
  onResendInvite,
  className,
}: UserRoleManagementProps) {
  const [searchQuery, setSearchQuery] = useState("");

  const filteredUsers = useMemo<User[]>(
    () =>
      users.filter((user) =>
        [user.name, user.email, user.role]
          .join(" ")
          .toLowerCase()
          .includes(searchQuery.toLowerCase()),
      ),
    [users, searchQuery],
  );

  return (
    <div className={cn("space-y-4", className)}>
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">User & Role Management</h2>
        <InviteUserDialog onInviteUser={onInviteUser} />
      </div>

      <div className="flex items-center space-x-2">
        <div className="relative flex-1">
          <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search users..."
            className="pl-8"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      <UserRoleTable
        users={filteredUsers}
        searchQuery={searchQuery}
        onUpdateUserRole={onUpdateUserRole}
        onRemoveUser={onRemoveUser}
        onResendInvite={onResendInvite}
      />
    </div>
  );
}
