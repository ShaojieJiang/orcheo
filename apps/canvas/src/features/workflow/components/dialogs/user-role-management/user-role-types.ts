export interface User {
  id: string;
  name: string;
  email: string;
  role: "owner" | "admin" | "editor" | "viewer";
  avatar: string;
  status: "active" | "invited" | "disabled";
  lastActive?: string;
}

export interface UserRoleManagementProps {
  users?: User[];
  onInviteUser?: (
    user: Omit<User, "id" | "avatar" | "status" | "lastActive">,
  ) => void;
  onUpdateUserRole?: (id: string, role: User["role"]) => void;
  onRemoveUser?: (id: string) => void;
  onResendInvite?: (id: string) => void;
  className?: string;
}
