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
        <img src="/favicon.svg" alt="Orcheo Logo" className="h-6 w-6" />
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
