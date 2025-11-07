import React, { useState } from "react";
import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";
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
import { UserPlus } from "lucide-react";
import type { User } from "@/features/workflow/components/dialogs/user-role-management/user-role-types";

interface InviteUserDialogProps {
  onInviteUser?: (
    user: Omit<User, "id" | "avatar" | "status" | "lastActive">,
  ) => void;
}

export default function InviteUserDialog({
  onInviteUser,
}: InviteUserDialogProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [newUser, setNewUser] = useState<{
    name: string;
    email: string;
    role: User["role"];
  }>({
    name: "",
    email: "",
    role: "editor",
  });

  const resetForm = () => {
    setNewUser({
      name: "",
      email: "",
      role: "editor",
    });
  };

  const handleInvite = () => {
    if (!newUser.name.trim() || !newUser.email.trim()) {
      return;
    }

    onInviteUser?.(newUser);
    resetForm();
    setIsOpen(false);
  };

  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) {
      resetForm();
    }
    setIsOpen(nextOpen);
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button>
          <UserPlus className="mr-2 h-4 w-4" />
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
              htmlFor="invite-name"
              className="text-right text-sm font-medium"
            >
              Name
            </label>
            <Input
              id="invite-name"
              value={newUser.name}
              onChange={(event) =>
                setNewUser({ ...newUser, name: event.target.value })
              }
              className="col-span-3"
              placeholder="John Doe"
            />
          </div>
          <div className="grid grid-cols-4 items-center gap-4">
            <label
              htmlFor="invite-email"
              className="text-right text-sm font-medium"
            >
              Email
            </label>
            <Input
              id="invite-email"
              type="email"
              value={newUser.email}
              onChange={(event) =>
                setNewUser({ ...newUser, email: event.target.value })
              }
              className="col-span-3"
              placeholder="builder@orcheo.dev"
            />
          </div>
          <div className="grid grid-cols-4 items-center gap-4">
            <label
              htmlFor="invite-role"
              className="text-right text-sm font-medium"
            >
              Role
            </label>
            <Select
              value={newUser.role}
              onValueChange={(role: User["role"]) =>
                setNewUser({ ...newUser, role })
              }
            >
              <SelectTrigger id="invite-role" className="col-span-3">
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
          <Button variant="outline" onClick={() => handleOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleInvite}>Send Invitation</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
