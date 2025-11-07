import React from "react";
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
import { ChevronDown, Folder, Plus } from "lucide-react";

export default function ProjectSwitcher() {
  return (
    <div className="flex items-center gap-4 lg:gap-6">
      <Link
        to="/"
        className="flex items-center gap-2 whitespace-nowrap font-semibold"
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
            <span className="hidden sm:inline">My Projects</span>
            <span className="sm:hidden">Projects</span>
            <ChevronDown className="ml-1 h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-56">
          <DropdownMenuLabel>Projects</DropdownMenuLabel>
          <DropdownMenuSeparator />
          {[
            { label: "Marketing Automations", query: "marketing" },
            { label: "Customer Onboarding", query: "onboarding" },
            { label: "Data Processing", query: "data" },
          ].map((project) => (
            <DropdownMenuItem key={project.query}>
              <Link
                to={`/workflow-canvas?project=${project.query}`}
                className="flex w-full items-center"
              >
                {project.label}
              </Link>
            </DropdownMenuItem>
          ))}
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
  );
}
