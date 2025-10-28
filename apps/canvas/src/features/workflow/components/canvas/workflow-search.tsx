import React, { useState, useEffect, useRef } from "react";
import { Search, X, ArrowUp, ArrowDown } from "lucide-react";
import { Input } from "@/design-system/ui/input";
import { Button } from "@/design-system/ui/button";
import { Badge } from "@/design-system/ui/badge";
import { cn } from "@/lib/utils";

interface WorkflowSearchProps {
  onSearch: (query: string) => void;
  onHighlightNext: () => void;
  onHighlightPrevious: () => void;
  onClose: () => void;
  matchCount: number;
  currentMatchIndex: number;
  isOpen: boolean;
  className?: string;
}

export default function WorkflowSearch({
  onSearch,
  onHighlightNext,
  onHighlightPrevious,
  onClose,
  matchCount,
  currentMatchIndex,
  isOpen,
  className,
}: WorkflowSearchProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  useEffect(() => {
    const targetWindow = typeof window !== "undefined" ? window : undefined;
    if (!targetWindow) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (!isOpen) {
        return;
      }

      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }

      if (event.key === "Enter") {
        if (event.shiftKey) {
          onHighlightPrevious();
        } else {
          onHighlightNext();
        }
      }
    };

    targetWindow.addEventListener("keydown", handleKeyDown);
    return () => targetWindow.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose, onHighlightNext, onHighlightPrevious]);

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const query = e.target.value;
    setSearchQuery(query);
    onSearch(query);
  };

  if (!isOpen) return null;

  return (
    <div
      className={cn(
        "absolute top-4 left-1/2 transform -translate-x-1/2 z-10 flex items-center bg-background border border-border rounded-md shadow-md",
        className,
      )}
      data-testid="workflow-search"
    >
      <div className="relative flex items-center w-80">
        <Search className="absolute left-2 h-4 w-4 text-muted-foreground" />

        <Input
          ref={inputRef}
          value={searchQuery}
          onChange={handleSearchChange}
          placeholder="Search nodes..."
          className="pl-8 pr-16 h-9 focus-visible:ring-1"
        />

        {searchQuery && (
          <Button
            variant="ghost"
            size="icon"
            className="absolute right-0 h-9 w-9"
            onClick={() => {
              setSearchQuery("");
              onSearch("");
            }}
          >
            <X className="h-4 w-4" />
          </Button>
        )}
      </div>

      <div className="flex items-center px-2 border-l border-border h-9">
        {matchCount > 0 ? (
          <Badge variant="secondary" className="mr-2">
            {currentMatchIndex + 1} of {matchCount}
          </Badge>
        ) : (
          searchQuery && (
            <Badge variant="outline" className="mr-2 text-muted-foreground">
              No matches
            </Badge>
          )
        )}

        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          onClick={onHighlightPrevious}
          disabled={matchCount === 0}
        >
          <ArrowUp className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          onClick={onHighlightNext}
          disabled={matchCount === 0}
        >
          <ArrowDown className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 ml-1"
          onClick={onClose}
        >
          <X className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
