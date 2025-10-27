import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
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
  Search,
  ChevronDown,
  ChevronRight,
  Command,
  Bell,
  User,
  Settings,
  LogOut,
  HelpCircle,
  Folder,
  Plus,
  MoreHorizontal,
  Key,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/design-system/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/design-system/ui/dialog";
import { Input } from "@/design-system/ui/input";
import CredentialsVault from "@features/workflow/components/dialogs/credentials-vault";
import type {
  Credential,
  CredentialInput,
} from "@features/workflow/types/credential-vault";

interface TopNavigationProps {
  currentWorkflow?: {
    name: string;
    path?: string[];
  };
  className?: string;
  credentials?: Credential[];
  isCredentialsLoading?: boolean;
  onAddCredential?: (credential: CredentialInput) => Promise<void> | void;
  onDeleteCredential?: (id: string) => Promise<void> | void;
}

export default function TopNavigation({
  currentWorkflow,
  className,
  credentials = [],
  isCredentialsLoading = false,
  onAddCredential,
  onDeleteCredential,
}: TopNavigationProps) {
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);
  const [isVaultOpen, setIsVaultOpen] = useState(false);
  const [windowWidth, setWindowWidth] = useState(
    typeof window !== "undefined" ? window.innerWidth : 0,
  );

  useEffect(() => {
    const handleResize = () => {
      setWindowWidth(window.innerWidth);
    };

    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
    };
  }, []);

  // Function to determine how many path items to show based on screen width
  const getVisiblePathItems = () => {
    if (!currentWorkflow?.path) return [];

    const totalItems = currentWorkflow.path.length;

    if (windowWidth < 640) {
      // Small screens
      // Show only first and last if there are more than 2 items
      if (totalItems > 2) {
        return [
          { index: 0, item: currentWorkflow.path[0] },
          { index: -1, item: "..." },
          { index: totalItems - 1, item: currentWorkflow.path[totalItems - 1] },
        ];
      }
    } else if (windowWidth < 768) {
      // Medium screens
      // Show first, last and one in between if there are more than 3 items
      if (totalItems > 3) {
        return [
          { index: 0, item: currentWorkflow.path[0] },
          { index: -1, item: "..." },
          { index: totalItems - 1, item: currentWorkflow.path[totalItems - 1] },
        ];
      }
    }

    // Default: show all items
    return currentWorkflow.path.map((item, index) => ({ index, item }));
  };

  return (
    <header
      className={cn(
        "flex h-14 items-center border-b border-border bg-background px-4 lg:px-6",
        className,
      )}
    >
      <div className="flex items-center gap-4 lg:gap-6">
        <Link
          to="/"
          className="flex items-center gap-2 font-semibold whitespace-nowrap"
        >
          <div className="flex h-6 w-6 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-4 w-4"
            >
              <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
            </svg>
          </div>
          <span>Orcheo Canvas</span>
        </Link>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" className="flex items-center gap-1">
              <Folder className="mr-1 h-4 w-4" />

              <span className="sm:inline hidden">My Projects</span>
              <span className="sm:hidden">Projects</span>
              <ChevronDown className="ml-1 h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-56">
            <DropdownMenuLabel>Projects</DropdownMenuLabel>
            <DropdownMenuSeparator />

            <DropdownMenuItem>
              <Link
                to="/workflow-canvas?project=marketing"
                className="flex w-full items-center"
              >
                Marketing Automations
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem>
              <Link
                to="/workflow-canvas?project=onboarding"
                className="flex w-full items-center"
              >
                Customer Onboarding
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem>
              <Link
                to="/workflow-canvas?project=data"
                className="flex w-full items-center"
              >
                Data Processing
              </Link>
            </DropdownMenuItem>
            <DropdownMenuSeparator />

            <DropdownMenuItem>
              <Link
                to="/workflow-canvas?new=true"
                className="flex w-full items-center"
              >
                <Plus className="mr-2 h-4 w-4" />
                Create New Project
              </Link>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {currentWorkflow && (
        <div className="ml-4 flex items-center text-sm text-muted-foreground overflow-hidden">
          {currentWorkflow.path ? (
            <div className="flex items-center overflow-hidden">
              {getVisiblePathItems().map((pathItem, idx) => (
                <React.Fragment key={idx}>
                  {pathItem.index === -1 ? (
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="sm" className="h-6 px-1">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="start" className="w-48">
                        {currentWorkflow.path
                          .slice(1, -1)
                          .map((item, index) => (
                            <DropdownMenuItem key={index}>
                              <Link to="/" className="flex w-full items-center">
                                {item}
                              </Link>
                            </DropdownMenuItem>
                          ))}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  ) : (
                    <>
                      <Link
                        to="/"
                        className="hover:text-foreground truncate max-w-[100px] sm:max-w-[150px]"
                      >
                        {pathItem.item}
                      </Link>
                      {idx < getVisiblePathItems().length - 1 && (
                        <ChevronRight className="mx-1 h-4 w-4 flex-shrink-0" />
                      )}
                    </>
                  )}
                </React.Fragment>
              ))}
              <ChevronRight className="mx-1 h-4 w-4 flex-shrink-0" />

              <span className="font-medium text-foreground truncate max-w-[120px] sm:max-w-[200px]">
                {currentWorkflow.name}
              </span>
            </div>
          ) : (
            <span className="font-medium text-foreground truncate">
              {currentWorkflow.name}
            </span>
          )}
        </div>
      )}

      <div className="ml-auto flex items-center gap-2">
        <Dialog open={commandPaletteOpen} onOpenChange={setCommandPaletteOpen}>
          <DialogTrigger asChild>
            <Button
              variant="outline"
              className="hidden items-center gap-1 sm:flex"
              onClick={() => setCommandPaletteOpen(true)}
            >
              <Search className="mr-1 h-4 w-4" />

              <span>Search</span>
              <kbd className="pointer-events-none ml-auto inline-flex h-5 select-none items-center gap-1 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground">
                <span className="text-xs">⌘</span>K
              </kbd>
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-[550px]">
            <DialogHeader>
              <DialogTitle>Search</DialogTitle>
              <DialogDescription>
                Search for workflows, nodes, or actions
              </DialogDescription>
            </DialogHeader>
            <div className="flex items-center border-b py-2">
              <Search className="mr-2 h-4 w-4 shrink-0 opacity-50" />

              <Input
                className="flex h-10 w-full rounded-md border-0 bg-transparent py-3 text-sm outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50"
                placeholder="Type to search..."
                autoFocus
              />
            </div>
            <div className="mt-2 space-y-1">
              <p className="text-xs text-muted-foreground">Recent searches</p>
              <div className="grid gap-1">
                <Button
                  variant="ghost"
                  className="justify-start text-sm"
                  onClick={() => setCommandPaletteOpen(false)}
                >
                  <Folder className="mr-2 h-4 w-4" />

                  <span>Customer Onboarding</span>
                  <Badge variant="outline" className="ml-auto">
                    Workflow
                  </Badge>
                </Button>
                <Button
                  variant="ghost"
                  className="justify-start text-sm"
                  onClick={() => setCommandPaletteOpen(false)}
                >
                  <Command className="mr-2 h-4 w-4" />

                  <span>HTTP Request</span>
                  <Badge variant="outline" className="ml-auto">
                    Node
                  </Badge>
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>

        <Button variant="ghost" size="icon">
          <Bell className="h-5 w-5" />
        </Button>

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
              <Link to="/profile" className="flex items-center w-full">
                <User className="mr-2 h-4 w-4" />

                <span>Profile</span>
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem>
              <Link to="/settings" className="flex items-center w-full">
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
              <div className="flex items-center w-full">
                <Key className="mr-2 h-4 w-4" />
                <span>Credential Vault</span>
              </div>
            </DropdownMenuItem>
            <DropdownMenuItem>
              <Link to="/help-support" className="flex items-center w-full">
                <HelpCircle className="mr-2 h-4 w-4" />

                <span>Help & Support</span>
              </Link>
            </DropdownMenuItem>
            <DropdownMenuSeparator />

            <DropdownMenuItem>
              <Link to="/login" className="flex items-center w-full">
                <LogOut className="mr-2 h-4 w-4" />

                <span>Log out</span>
              </Link>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
        <Dialog open={isVaultOpen} onOpenChange={setIsVaultOpen}>
          <DialogContent className="max-w-4xl">
            <CredentialsVault
              credentials={credentials}
              isLoading={isCredentialsLoading}
              onAddCredential={onAddCredential}
              onDeleteCredential={onDeleteCredential}
            />
          </DialogContent>
        </Dialog>
      </div>
    </header>
  );
}
