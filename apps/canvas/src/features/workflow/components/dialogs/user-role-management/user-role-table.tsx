import React from "react";
import { Button } from "@/design-system/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/design-system/ui/avatar";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/design-system/ui/table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/design-system/ui/dropdown-menu";
import { Mail, MoreHorizontal, Edit, Shield, Trash } from "lucide-react";
import {
  RoleBadge,
  StatusBadge,
} from "@/features/workflow/components/dialogs/user-role-management/role-badges";
import type { User } from "@/features/workflow/components/dialogs/user-role-management/user-role-types";

interface UserRoleTableProps {
  users: User[];
  searchQuery: string;
  onUpdateUserRole?: (id: string, role: User["role"]) => void;
  onRemoveUser?: (id: string) => void;
  onResendInvite?: (id: string) => void;
}

export default function UserRoleTable({
  users,
  searchQuery,
  onRemoveUser,
  onResendInvite,
  onUpdateUserRole,
}: UserRoleTableProps) {
  if (users.length === 0) {
    return (
      <div className="rounded-md border p-6 text-center">
        <div className="text-muted-foreground">
          No users found
          {searchQuery && (
            <p className="text-sm">Try adjusting your search query</p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>User</TableHead>
            <TableHead>Role</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Last Active</TableHead>
            <TableHead className="w-[80px]"></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {users.map((user) => (
            <TableRow key={user.id}>
              <TableCell>
                <div className="flex items-center gap-3">
                  <Avatar>
                    <AvatarImage src={user.avatar} alt={user.name} />
                    <AvatarFallback>
                      {user.name
                        .split(" ")
                        .map((part) => part[0])
                        .join("")
                        .toUpperCase()}
                    </AvatarFallback>
                  </Avatar>
                  <div>
                    <div className="font-medium">{user.name}</div>
                    <div className="text-sm text-muted-foreground">
                      {user.email}
                    </div>
                  </div>
                </div>
              </TableCell>
              <TableCell>
                <RoleBadge role={user.role} />
              </TableCell>
              <TableCell>
                <StatusBadge status={user.status} />
              </TableCell>
              <TableCell>
                {user.lastActive
                  ? new Date(user.lastActive).toLocaleDateString()
                  : "Never"}
              </TableCell>
              <TableCell>
                <ActionsMenu
                  user={user}
                  onRemoveUser={onRemoveUser}
                  onResendInvite={onResendInvite}
                  onUpdateUserRole={onUpdateUserRole}
                />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

interface ActionsMenuProps {
  user: User;
  onUpdateUserRole?: (id: string, role: User["role"]) => void;
  onRemoveUser?: (id: string) => void;
  onResendInvite?: (id: string) => void;
}

function ActionsMenu({
  user,
  onRemoveUser,
  onResendInvite,
  onUpdateUserRole,
}: ActionsMenuProps) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="h-8 w-8">
          <MoreHorizontal className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>Actions</DropdownMenuLabel>
        {user.role !== "owner" && (
          <>
            <DropdownMenuItem>
              <Edit className="mr-2 h-4 w-4" />
              Edit
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuLabel className="text-xs font-normal text-muted-foreground">
              Change Role
            </DropdownMenuLabel>
            <DropdownMenuItem
              onClick={() => onUpdateUserRole?.(user.id, "admin")}
            >
              <Shield className="mr-2 h-4 w-4" />
              Admin
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={() => onUpdateUserRole?.(user.id, "editor")}
            >
              <Edit className="mr-2 h-4 w-4" />
              Editor
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={() => onUpdateUserRole?.(user.id, "viewer")}
            >
              <Shield className="mr-2 h-4 w-4" />
              Viewer
            </DropdownMenuItem>
            <DropdownMenuSeparator />
          </>
        )}
        {user.status === "invited" && (
          <DropdownMenuItem onClick={() => onResendInvite?.(user.id)}>
            <Mail className="mr-2 h-4 w-4" />
            Resend Invite
          </DropdownMenuItem>
        )}
        {user.role !== "owner" && (
          <DropdownMenuItem
            className="text-destructive focus:text-destructive"
            onClick={() => onRemoveUser?.(user.id)}
          >
            <Trash className="mr-2 h-4 w-4" />
            Remove
          </DropdownMenuItem>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
