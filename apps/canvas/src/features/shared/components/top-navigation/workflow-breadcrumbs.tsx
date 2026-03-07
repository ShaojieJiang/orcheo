import React, { useMemo } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/design-system/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/design-system/ui/dropdown-menu";
import { ChevronRight, MoreHorizontal } from "lucide-react";

interface WorkflowBreadcrumbsProps {
  currentWorkflow: {
    name: string;
    path?: string[];
  };
  windowWidth: number;
}

export default function WorkflowBreadcrumbs({
  currentWorkflow,
  windowWidth,
}: WorkflowBreadcrumbsProps) {
  const normalizedPath = useMemo(() => {
    const path = currentWorkflow.path ?? [];
    if (path.length === 0) {
      return path;
    }

    const lastPathItem = path[path.length - 1];
    if (lastPathItem === currentWorkflow.name) {
      return path.slice(0, -1);
    }

    return path;
  }, [currentWorkflow.name, currentWorkflow.path]);

  const visibleItems = useMemo(
    () => getVisiblePathItems(normalizedPath, windowWidth),
    [normalizedPath, windowWidth],
  );

  if (normalizedPath.length === 0) {
    return (
      <span className="truncate font-medium text-foreground">
        {currentWorkflow.name}
      </span>
    );
  }

  return (
    <div className="ml-4 flex items-center overflow-hidden text-sm text-muted-foreground">
      <div className="flex items-center overflow-hidden">
        {visibleItems.map((pathItem, idx) => (
          <React.Fragment key={`${pathItem.item}-${idx}`}>
            {pathItem.index === -1 ? (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="sm" className="h-6 px-1">
                    <MoreHorizontal className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start" className="w-48">
                  {normalizedPath.slice(1).map((item) => (
                    <DropdownMenuItem key={item}>
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
                  className="max-w-[100px] truncate hover:text-foreground sm:max-w-[150px]"
                >
                  {pathItem.item}
                </Link>
                {idx < visibleItems.length - 1 && (
                  <ChevronRight className="mx-1 h-4 w-4 flex-shrink-0" />
                )}
              </>
            )}
          </React.Fragment>
        ))}
        <ChevronRight className="mx-1 h-4 w-4 flex-shrink-0" />
        <span className="max-w-[120px] truncate text-foreground sm:max-w-[200px]">
          {currentWorkflow.name}
        </span>
      </div>
    </div>
  );
}

function getVisiblePathItems(path: string[], windowWidth: number) {
  const totalItems = path.length;

  if (totalItems === 0) {
    return [];
  }

  if (windowWidth < 640 && totalItems > 2) {
    return [
      { index: 0, item: path[0] },
      { index: -1, item: "..." },
      { index: totalItems - 1, item: path[totalItems - 1] },
    ];
  }

  if (windowWidth < 768 && totalItems > 3) {
    return [
      { index: 0, item: path[0] },
      { index: -1, item: "..." },
      { index: totalItems - 1, item: path[totalItems - 1] },
    ];
  }

  return path.map((item, index) => ({ index, item }));
}
