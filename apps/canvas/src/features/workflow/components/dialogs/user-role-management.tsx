import React, { useState } from "react";
import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/design-system/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/design-system/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/design-system/ui/select";
import { Badge } from "@/design-system/ui/badge";
import { Avatar, AvatarFallback, AvatarImage } from "@/design-system/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/design-system/ui/dropdown-menu";
import {
  Search,
  Plus,
  MoreHorizontal,
  Mail,
  UserPlus,
  Shield,
  Edit,
  Trash,
  CheckCircle,
  XCircle,
} from "lucide-react";

interface User {
  id: string;
  name: string;
  email: string;
  role: "owner" | "admin" | "editor" | "viewer";
  avatar: string;
  status: "active" | "invited" | "disabled";
  lastActive?: string;
}

interface UserRoleManagementProps {
  users?: User[];
  onInviteUser?: (
    user: Omit<User, "id" | "avatar" | "status" | "lastActive">,
  ) => void;
  onUpdateUserRole?: (id: string, role: User["role"]) => void;
  onRemoveUser?: (id: string) => void;
  onResendInvite?: (id: string) => void;
  className?: string;
}

export default function UserRoleManagement({
  users = [],
  onInviteUser,
  onUpdateUserRole,
  onRemoveUser,
  onResendInvite,
  className,
}: UserRoleManagementProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [isInviteDialogOpen, setIsInviteDialogOpen] = useState(false);
  const [newUser, setNewUser] = useState<{
    name: string;
    email: string;
    role: User["role"];
  }>({
    name: "",
    email: "",
    role: "editor",
  });

  // Filter users based on search query
  const filteredUsers = users.filter(
    (user) =>
      user.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      user.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
      user.role.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  const handleInviteUser = () => {
    if (onInviteUser && newUser.email.trim() && newUser.name.trim()) {
      onInviteUser(newUser);
      setNewUser({
        name: "",
        email: "",
        role: "editor",
      });
      setIsInviteDialogOpen(false);
    }
  };

  const getRoleBadge = (role: string) => {
    switch (role) {
      case "owner":
        return (
          <Badge className="bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400">
            <Shield className="h-3 w-3 mr-1" />
            Owner
          </Badge>
        );

      case "admin":
        return (
          <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400">
            <Shield className="h-3 w-3 mr-1" />
            Admin
          </Badge>
        );

      case "editor":
        return (
          <Badge className="bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400">
            Edit
          </Badge>
        );

      case "viewer":
        return (
          <Badge className="bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400">
            View
          </Badge>
        );

      default:
        return null;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "active":
        return (
          <Badge
            variant="outline"
            className="bg-green-100 text-green-800 border-green-200 dark:bg-green-900/30 dark:text-green-400 dark:border-green-800"
          >
            <CheckCircle className="h-3 w-3 mr-1" />
            Active
          </Badge>
        );

      case "invited":
        return (
          <Badge
            variant="outline"
            className="bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-900/30 dark:text-amber-400 dark:border-amber-800"
          >
            Invited
          </Badge>
        );

      case "disabled":
        return (
          <Badge
            variant="outline"
            className="bg-red-100 text-red-800 border-red-200 dark:bg-red-900/30 dark:text-red-400 dark:border-red-800"
          >
            <XCircle className="h-3 w-3 mr-1" />
            Disabled
          </Badge>
        );

      default:
        return null;
    }
  };

  return (
    <div className={`space-y-4 ${className}`}>
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-bold">User & Role Management</h2>
        <Dialog open={isInviteDialogOpen} onOpenChange={setIsInviteDialogOpen}>
          <DialogTrigger asChild>
            <Button>
              <UserPlus className="h-4 w-4 mr-2" />
              Invite User
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-[500px]">
            <DialogHeader>
              <DialogTitle>Invite New User</DialogTitle>
              <DialogDescription>
                Send an invitation to collaborate on this project.
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <div className="grid grid-cols-4 items-center gap-4">
                <label
                  htmlFor="name"
                  className="text-right text-sm font-medium"
                >
                  Name
                </label>
                <Input
                  id="name"
                  value={newUser.name}
                  onChange={(e) =>
                    setNewUser({ ...newUser, name: e.target.value })
                  }
                  className="col-span-3"
                  placeholder="John Doe"
                />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <label
                  htmlFor="email"
                  className="text-right text-sm font-medium"
                >
                  Email
                </label>
                <Input
                  id="email"
                  type="email"
                  value={newUser.email}
                  onChange={(e) =>
                    setNewUser({ ...newUser, email: e.target.value })
                  }
                  className="col-span-3"
                  placeholder="builder@orcheo.dev"
                />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <label
                  htmlFor="role"
                  className="text-right text-sm font-medium"
                >
                  Role
                </label>
                <Select
                  value={newUser.role}
                  onValueChange={(value: User["role"]) =>
                    setNewUser({ ...newUser, role: value })
                  }
                >
                  <SelectTrigger className="col-span-3">
                    <SelectValue placeholder="Select role" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="admin">Admin</SelectItem>
                    <SelectItem value="editor">Editor</SelectItem>
                    <SelectItem value="viewer">Viewer</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setIsInviteDialogOpen(false)}
              >
                Cancel
              </Button>
              <Button onClick={handleInviteUser}>Send Invitation</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
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

      <div className="border rounded-md">
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
            {filteredUsers.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center py-8">
                  <div className="text-muted-foreground">
                    No users found
                    {searchQuery && (
                      <p className="text-sm">Try adjusting your search query</p>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              filteredUsers.map((user) => (
                <TableRow key={user.id}>
                  <TableCell>
                    <div className="flex items-center gap-3">
                      <Avatar>
                        <AvatarImage src={user.avatar} alt={user.name} />

                        <AvatarFallback>
                          {user.name
                            .split(" ")
                            .map((n) => n[0])
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
                  <TableCell>{getRoleBadge(user.role)}</TableCell>
                  <TableCell>{getStatusBadge(user.status)}</TableCell>
                  <TableCell>
                    {user.lastActive
                      ? new Date(user.lastActive).toLocaleDateString()
                      : "Never"}
                  </TableCell>
                  <TableCell>
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
                              <Edit className="h-4 w-4 mr-2" />
                              Edit
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />

                            <DropdownMenuLabel className="text-xs font-normal text-muted-foreground">
                              Change Role
                            </DropdownMenuLabel>
                            <DropdownMenuItem
                              onClick={() =>
                                onUpdateUserRole &&
                                onUpdateUserRole(user.id, "admin")
                              }
                            >
                              <Shield className="h-4 w-4 mr-2" />
                              Admin
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={() =>
                                onUpdateUserRole &&
                                onUpdateUserRole(user.id, "editor")
                              }
                            >
                              <Edit className="h-4 w-4 mr-2" />
                              Editor
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={() =>
                                onUpdateUserRole &&
                                onUpdateUserRole(user.id, "viewer")
                              }
                            >
                              <Shield className="h-4 w-4 mr-2" />
                              Viewer
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                          </>
                        )}
                        {user.status === "invited" && (
                          <DropdownMenuItem
                            onClick={() =>
                              onResendInvite && onResendInvite(user.id)
                            }
                          >
                            <Mail className="h-4 w-4 mr-2" />
                            Resend Invite
                          </DropdownMenuItem>
                        )}
                        {user.role !== "owner" && (
                          <DropdownMenuItem
                            className="text-destructive focus:text-destructive"
                            onClick={() =>
                              onRemoveUser && onRemoveUser(user.id)
                            }
                          >
                            <Trash className="h-4 w-4 mr-2" />
                            Remove
                          </DropdownMenuItem>
                        )}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
