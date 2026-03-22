import React, {
  useCallback,
  useEffect,
  useRef,
  useMemo,
  useState,
} from "react";
import { Link } from "react-router-dom";
import { Button } from "@/design-system/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/design-system/ui/dropdown-menu";
import { ChevronRight, MoreHorizontal, Check, X } from "lucide-react";

interface WorkflowBreadcrumbsProps {
  currentWorkflow: {
    name: string;
    path?: string[];
    onNameChange?: (name: string) => void;
  };
  windowWidth: number;
}

export default function WorkflowBreadcrumbs({
  currentWorkflow,
  windowWidth,
}: WorkflowBreadcrumbsProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(currentWorkflow.name);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!isEditing) {
      setEditValue(currentWorkflow.name);
    }
  }, [currentWorkflow.name, isEditing]);

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

  const commitEdit = useCallback(() => {
    const trimmed = editValue.trim();
    if (trimmed && trimmed !== currentWorkflow.name) {
      currentWorkflow.onNameChange?.(trimmed);
    }
    setIsEditing(false);
  }, [editValue, currentWorkflow]);

  const cancelEdit = useCallback(() => {
    setEditValue(currentWorkflow.name);
    setIsEditing(false);
  }, [currentWorkflow.name]);

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      if (event.key === "Enter") {
        commitEdit();
      } else if (event.key === "Escape") {
        cancelEdit();
      }
    },
    [commitEdit, cancelEdit],
  );

  const isEditable = Boolean(currentWorkflow.onNameChange);

  const nameElement = isEditing ? (
    <span className="inline-flex items-center gap-1">
      <input
        ref={inputRef}
        type="text"
        className="h-6 w-[140px] rounded border border-border bg-background px-1 text-sm text-foreground outline-none focus:ring-1 focus:ring-ring sm:w-[180px]"
        value={editValue}
        onChange={(e) => setEditValue(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={commitEdit}
      />
      <Button
        variant="ghost"
        size="sm"
        className="h-5 w-5 p-0"
        onMouseDown={(e) => e.preventDefault()}
        onClick={commitEdit}
      >
        <Check className="h-3 w-3" />
      </Button>
      <Button
        variant="ghost"
        size="sm"
        className="h-5 w-5 p-0"
        onMouseDown={(e) => e.preventDefault()}
        onClick={cancelEdit}
      >
        <X className="h-3 w-3" />
      </Button>
    </span>
  ) : (
    <span
      data-testid="workflow-name-display"
      className={`max-w-[120px] truncate text-foreground sm:max-w-[200px] ${isEditable ? "cursor-pointer rounded px-0.5 hover:bg-muted" : ""}`}
      onDoubleClick={isEditable ? () => setIsEditing(true) : undefined}
      title={isEditable ? "Double-click to rename" : undefined}
    >
      {currentWorkflow.name}
    </span>
  );

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
        {nameElement}
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
        {nameElement}
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
