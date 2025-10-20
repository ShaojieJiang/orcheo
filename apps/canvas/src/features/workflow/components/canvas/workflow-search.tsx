import React, { useState, useEffect, useRef } from "react";
import { Search, X, ArrowUp, ArrowDown } from "lucide-react";
import { Input } from "@/design-system/ui/input";
import { Button } from "@/design-system/ui/button";
import { Badge } from "@/design-system/ui/badge";
import { cn } from "@/lib/utils";

interface WorkflowSearchProps {
  query: string;
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
  query,
  onSearch,
  onHighlightNext,
  onHighlightPrevious,
  onClose,
  matchCount,
  currentMatchIndex,
  isOpen,
  className,
}: WorkflowSearchProps) {
  const [searchQuery, setSearchQuery] = useState(query);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  useEffect(() => {
    setSearchQuery(query);
  }, [query]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.key.toLowerCase() === "f") {
        e.preventDefault();
        if (!isOpen) {
          onSearch(query);
        } else {
          inputRef.current?.focus();
        }
      } else if (e.key === "Escape" && isOpen) {
        e.preventDefault();
        onClose();
      } else if (e.key === "Enter") {
        if (e.shiftKey) {
          onHighlightPrevious();
        } else {
          onHighlightNext();
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onSearch, onClose, onHighlightNext, onHighlightPrevious, query]);

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
    >
      <div className="relative flex items-center w-80">
        <Search className="absolute left-2 h-4 w-4 text-muted-foreground" />

        <Input
          ref={inputRef}
          value={searchQuery}
          onChange={handleSearchChange}
          placeholder="Search nodes..."
          aria-label="Search workflow nodes"
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
            aria-label="Clear search"
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
          aria-label="Previous match"
        >
          <ArrowUp className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          onClick={onHighlightNext}
          disabled={matchCount === 0}
          aria-label="Next match"
        >
          <ArrowDown className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 ml-1"
          onClick={onClose}
          aria-label="Close search"
        >
          <X className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
