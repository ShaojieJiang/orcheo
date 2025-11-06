import { Button } from "@/design-system/ui/button";
import { Checkbox } from "@/design-system/ui/checkbox";
import { Label } from "@/design-system/ui/label";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/design-system/ui/popover";
import { Filter } from "lucide-react";
import { useCallback } from "react";
import { type WorkflowGalleryFilters } from "./types";

interface WorkflowFilterPopoverProps {
  filters: WorkflowGalleryFilters;
  onFiltersChange: (filters: WorkflowGalleryFilters) => void;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onApplyFilters: () => void;
}

const OWNER_OPTIONS = [
  {
    id: "owner-me",
    label: "Created by me",
    key: "me" as const,
  },
  {
    id: "owner-shared",
    label: "Shared with me",
    key: "shared" as const,
  },
];

const STATUS_OPTIONS = [
  {
    id: "status-active",
    label: "Active",
    key: "active" as const,
  },
  {
    id: "status-draft",
    label: "Draft",
    key: "draft" as const,
  },
  {
    id: "status-archived",
    label: "Archived",
    key: "archived" as const,
  },
];

const TAG_OPTIONS = [
  {
    id: "tag-favorite",
    label: "Favorite",
    key: "favorite" as const,
  },
  {
    id: "tag-template",
    label: "Template",
    key: "template" as const,
  },
  {
    id: "tag-production",
    label: "Production",
    key: "production" as const,
  },
  {
    id: "tag-development",
    label: "Development",
    key: "development" as const,
  },
];

export const WorkflowFilterPopover = ({
  filters,
  onFiltersChange,
  open,
  onOpenChange,
  onApplyFilters,
}: WorkflowFilterPopoverProps) => {
  const updateOwner = useCallback(
    (key: keyof WorkflowGalleryFilters["owner"]) =>
      (checked: boolean | "indeterminate") => {
        onFiltersChange({
          ...filters,
          owner: { ...filters.owner, [key]: Boolean(checked) },
        });
      },
    [filters, onFiltersChange],
  );

  const updateStatus = useCallback(
    (key: keyof WorkflowGalleryFilters["status"]) =>
      (checked: boolean | "indeterminate") => {
        onFiltersChange({
          ...filters,
          status: { ...filters.status, [key]: Boolean(checked) },
        });
      },
    [filters, onFiltersChange],
  );

  const updateTags = useCallback(
    (key: keyof WorkflowGalleryFilters["tags"]) =>
      (checked: boolean | "indeterminate") => {
        onFiltersChange({
          ...filters,
          tags: { ...filters.tags, [key]: Boolean(checked) },
        });
      },
    [filters, onFiltersChange],
  );

  return (
    <Popover open={open} onOpenChange={onOpenChange}>
      <PopoverTrigger asChild>
        <Button variant="outline" size="icon">
          <Filter className="h-4 w-4" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-80">
        <div className="space-y-4">
          <h4 className="font-medium">Filter Workflows</h4>

          <div className="space-y-2">
            <h5 className="text-sm font-medium">Owner</h5>
            <div className="flex flex-col gap-2">
              {OWNER_OPTIONS.map((option) => (
                <div key={option.id} className="flex items-center space-x-2">
                  <Checkbox
                    id={option.id}
                    checked={filters.owner[option.key]}
                    onCheckedChange={updateOwner(option.key)}
                  />
                  <Label htmlFor={option.id}>{option.label}</Label>
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <h5 className="text-sm font-medium">Status</h5>
            <div className="flex flex-col gap-2">
              {STATUS_OPTIONS.map((option) => (
                <div key={option.id} className="flex items-center space-x-2">
                  <Checkbox
                    id={option.id}
                    checked={filters.status[option.key]}
                    onCheckedChange={updateStatus(option.key)}
                  />
                  <Label htmlFor={option.id}>{option.label}</Label>
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <h5 className="text-sm font-medium">Tags</h5>
            <div className="flex flex-col gap-2">
              {TAG_OPTIONS.map((option) => (
                <div key={option.id} className="flex items-center space-x-2">
                  <Checkbox
                    id={option.id}
                    checked={filters.tags[option.key]}
                    onCheckedChange={updateTags(option.key)}
                  />
                  <Label htmlFor={option.id}>{option.label}</Label>
                </div>
              ))}
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button size="sm" onClick={onApplyFilters}>
              Apply Filters
            </Button>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
};
