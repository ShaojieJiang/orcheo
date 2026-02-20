import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/design-system/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/design-system/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/design-system/ui/dialog";
import { HelpCircle, Key, LogOut, Settings, User } from "lucide-react";
import CredentialsVault from "@features/workflow/components/dialogs/credentials-vault";
import { clearAuthSession } from "@features/auth/lib/auth-session";
import type {
  Credential,
  CredentialInput,
} from "@features/workflow/types/credential-vault";

interface AccountMenuProps {
  credentials: Credential[];
  isCredentialsLoading: boolean;
  onAddCredential?: (credential: CredentialInput) => Promise<void> | void;
  onDeleteCredential?: (id: string) => Promise<void> | void;
}

export default function AccountMenu({
  credentials,
  isCredentialsLoading,
  onAddCredential,
  onDeleteCredential,
}: AccountMenuProps) {
  const [isVaultOpen, setIsVaultOpen] = useState(false);
  const navigate = useNavigate();

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="rounded-full border-2 border-border"
          >
            <User className="h-5 w-5" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuLabel>My Account</DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem>
            <Link to="/profile" className="flex w-full items-center">
              <User className="mr-2 h-4 w-4" />
              <span>Profile</span>
            </Link>
          </DropdownMenuItem>
          <DropdownMenuItem>
            <Link to="/settings" className="flex w-full items-center">
              <Settings className="mr-2 h-4 w-4" />
              <span>Settings</span>
            </Link>
          </DropdownMenuItem>
          <DropdownMenuItem
            onSelect={(event) => {
              event.preventDefault();
              setIsVaultOpen(true);
            }}
            className="cursor-pointer"
          >
            <div className="flex w-full items-center">
              <Key className="mr-2 h-4 w-4" />
              <span>Credential Vault</span>
            </div>
          </DropdownMenuItem>
          <DropdownMenuItem>
            <Link to="/help-support" className="flex w-full items-center">
              <HelpCircle className="mr-2 h-4 w-4" />
              <span>Help & Support</span>
            </Link>
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            onSelect={() => {
              clearAuthSession();
              navigate("/login", { replace: true });
            }}
            className="cursor-pointer"
          >
            <div className="flex w-full items-center">
              <LogOut className="mr-2 h-4 w-4" />
              <span>Log out</span>
            </div>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <Dialog open={isVaultOpen} onOpenChange={setIsVaultOpen}>
        <DialogContent className="max-w-4xl">
          <DialogTitle className="sr-only">Credential Vault</DialogTitle>
          <DialogDescription className="sr-only">
            Manage, search, add, and remove credentials.
          </DialogDescription>
          <CredentialsVault
            credentials={credentials}
            isLoading={isCredentialsLoading}
            onAddCredential={onAddCredential}
            onDeleteCredential={onDeleteCredential}
          />
        </DialogContent>
      </Dialog>
    </>
  );
}
