import React, { useMemo, useState } from "react";
import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";
import { ScrollArea } from "@/design-system/ui/scroll-area";
import { Badge } from "@/design-system/ui/badge";
import { Search, FileJson, Table, Code, X } from "lucide-react";
import { cn } from "@/lib/utils";
import type {
  VariableInspectorView,
  VariablesMap,
} from "./variable-inspector-types";
import { VariableTreeView } from "./variable-inspector-tree";
import { VariableTableView } from "./variable-inspector-table";

interface VariableInspectorProps {
  variables?: VariablesMap;
  currentNodeId?: string;
  onClose?: () => void;
  className?: string;
}

export default function VariableInspector({
  variables = {},
  currentNodeId,
  onClose,
  className,
}: VariableInspectorProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedPaths, setExpandedPaths] = useState<string[]>([]);
  const [viewType, setViewType] = useState<VariableInspectorView>("tree");
  const [hiddenValues, setHiddenValues] = useState<string[]>([]);

  // Filter variables based on search query
  const filteredVariables = useMemo<VariablesMap>(() => {
    if (!searchQuery) {
      return variables;
    }

    return Object.entries(variables).reduce((acc, [key, value]) => {
      const matchKey = key.toLowerCase().includes(searchQuery.toLowerCase());
      const matchValue = JSON.stringify(value)
        .toLowerCase()
        .includes(searchQuery.toLowerCase());

      if (matchKey || matchValue) {
        acc[key] = value;
      }

      return acc;
    }, {} as VariablesMap);
  }, [searchQuery, variables]);

  const toggleExpand = (path: string) => {
    if (expandedPaths.includes(path)) {
      setExpandedPaths(expandedPaths.filter((p) => p !== path));
    } else {
      setExpandedPaths([...expandedPaths, path]);
    }
  };

  const toggleHideValue = (path: string) => {
    if (hiddenValues.includes(path)) {
      setHiddenValues(hiddenValues.filter((p) => p !== path));
    } else {
      setHiddenValues([...hiddenValues, path]);
    }
  };

  const copyToClipboard = (value: unknown) => {
    navigator.clipboard.writeText(
      typeof value === "object"
        ? JSON.stringify(value, null, 2)
        : String(value),
    );
  };

  return (
    <div
      className={cn(
        "flex flex-col border border-border rounded-lg bg-background shadow-lg",
        className,
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-border">
        <div className="flex items-center gap-3">
          <div className="flex flex-col">
            <h3 className="font-medium">Variable Inspector</h3>
            {currentNodeId && (
              <p className="text-xs text-muted-foreground">
                Current node: {currentNodeId}
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Search and view type */}
      <div className="flex items-center gap-2 p-3 border-b border-border">
        <div className="relative flex-1">
          <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />

          <Input
            placeholder="Search variables..."
            className="pl-8"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
        <div className="flex items-center border rounded-md overflow-hidden">
          <Button
            variant={viewType === "tree" ? "secondary" : "ghost"}
            size="sm"
            className="rounded-none px-3"
            onClick={() => setViewType("tree")}
          >
            <Code className="h-4 w-4 mr-1" />
            Tree
          </Button>
          <Button
            variant={viewType === "json" ? "secondary" : "ghost"}
            size="sm"
            className="rounded-none px-3"
            onClick={() => setViewType("json")}
          >
            <FileJson className="h-4 w-4 mr-1" />
            JSON
          </Button>
          <Button
            variant={viewType === "table" ? "secondary" : "ghost"}
            size="sm"
            className="rounded-none px-3"
            onClick={() => setViewType("table")}
          >
            <Table className="h-4 w-4 mr-1" />
            Table
          </Button>
        </div>
      </div>

      {/* Variables content */}
      <ScrollArea className="flex-1 p-3 h-[400px]">
        {Object.keys(filteredVariables).length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
            <p>No variables found</p>
            {searchQuery && (
              <p className="text-sm">Try adjusting your search query</p>
            )}
          </div>
        ) : viewType === "tree" ? (
          <VariableTreeView
            variables={filteredVariables}
            expandedPaths={expandedPaths}
            hiddenValues={hiddenValues}
            onToggleExpand={toggleExpand}
            onToggleHideValue={toggleHideValue}
            onCopy={copyToClipboard}
          />
        ) : viewType === "json" ? (
          <pre className="font-mono text-sm whitespace-pre-wrap">
            {JSON.stringify(filteredVariables, null, 2)}
          </pre>
        ) : (
          <VariableTableView
            variables={filteredVariables}
            hiddenValues={hiddenValues}
            onToggleHideValue={toggleHideValue}
            onCopy={copyToClipboard}
          />
        )}
      </ScrollArea>

      {/* Footer */}
      <div className="flex items-center justify-between p-3 border-t border-border">
        <div className="text-xs text-muted-foreground">
          {Object.keys(filteredVariables).length} variables
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline">Debug Mode</Badge>
        </div>
      </div>
    </div>
  );
}
