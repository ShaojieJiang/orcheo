import React from "react";
import { Badge } from "@/design-system/ui/badge";
import { Shield, Edit, Eye, CheckCircle, XCircle } from "lucide-react";
import type { User } from "@/features/workflow/components/dialogs/user-role-management/user-role-types";

interface RoleBadgeProps {
  role: User["role"];
}

interface StatusBadgeProps {
  status: User["status"];
}

export function RoleBadge({ role }: RoleBadgeProps) {
  switch (role) {
    case "owner":
      return (
        <Badge className="bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400">
          <Shield className="mr-1 h-3 w-3" />
          Owner
        </Badge>
      );
    case "admin":
      return (
        <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400">
          <Shield className="mr-1 h-3 w-3" />
          Admin
        </Badge>
      );
    case "editor":
      return (
        <Badge className="bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400">
          <Edit className="mr-1 h-3 w-3" />
          Edit
        </Badge>
      );
    case "viewer":
      return (
        <Badge className="bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400">
          <Eye className="mr-1 h-3 w-3" />
          View
        </Badge>
      );
    default:
      return null;
  }
}

export function StatusBadge({ status }: StatusBadgeProps) {
  switch (status) {
    case "active":
      return (
        <Badge
          variant="outline"
          className="border-green-200 bg-green-100 text-green-800 dark:border-green-800 dark:bg-green-900/30 dark:text-green-400"
        >
          <CheckCircle className="mr-1 h-3 w-3" />
          Active
        </Badge>
      );
    case "invited":
      return (
        <Badge
          variant="outline"
          className="border-amber-200 bg-amber-100 text-amber-800 dark:border-amber-800 dark:bg-amber-900/30 dark:text-amber-400"
        >
          Invited
        </Badge>
      );
    case "disabled":
      return (
        <Badge
          variant="outline"
          className="border-red-200 bg-red-100 text-red-800 dark:border-red-800 dark:bg-red-900/30 dark:text-red-400"
        >
          <XCircle className="mr-1 h-3 w-3" />
          Disabled
        </Badge>
      );
    default:
      return null;
  }
}
