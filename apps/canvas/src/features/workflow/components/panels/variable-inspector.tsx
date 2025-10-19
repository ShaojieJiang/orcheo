import React, { useState } from "react";
import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";
import { Label } from "@/design-system/ui/label";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/design-system/ui/tabs";
import { ScrollArea } from "@/design-system/ui/scroll-area";
import { Badge } from "@/design-system/ui/badge";
import {
  Search,
  ChevronRight,
  ChevronDown,
  Copy,
  FileJson,
  Table,
  Code,
  X,
  Eye,
  EyeOff,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface VariableInspectorProps {
  variables?: Record<string, any>;
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
  const [viewType, setViewType] = useState<"tree" | "json" | "table">("tree");
  const [hiddenValues, setHiddenValues] = useState<string[]>([]);

  // Filter variables based on search query
  const filteredVariables = searchQuery
    ? Object.entries(variables).reduce(
        (acc, [key, value]) => {
          if (
            key.toLowerCase().includes(searchQuery.toLowerCase()) ||
            JSON.stringify(value)
              .toLowerCase()
              .includes(searchQuery.toLowerCase())
          ) {
            acc[key] = value;
          }
          return acc;
        },
        {} as Record<string, any>,
      )
    : variables;

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

  const copyToClipboard = (value: any) => {
    navigator.clipboard.writeText(
      typeof value === "object"
        ? JSON.stringify(value, null, 2)
        : String(value),
    );
  };

  const renderTreeValue = (
    value: any,
    path: string,
    depth = 0,
    isLast = true,
  ) => {
    const isExpanded = expandedPaths.includes(path);
    const isHidden = hiddenValues.includes(path);
    const isObject =
      value !== null && typeof value === "object" && !Array.isArray(value);
    const isArray = Array.isArray(value);
    const hasChildren = isObject || isArray;

    const getValueDisplay = () => {
      if (isHidden) return "••••••••";

      if (value === null)
        return <span className="text-muted-foreground">null</span>;

      if (value === undefined)
        return <span className="text-muted-foreground">undefined</span>;

      if (typeof value === "string") return `"${value}"`;
      if (typeof value === "number")
        return (
          <span className="text-blue-500 dark:text-blue-400">{value}</span>
        );

      if (typeof value === "boolean")
        return (
          <span className="text-amber-500 dark:text-amber-400">
            {String(value)}
          </span>
        );

      if (isArray) return `Array(${value.length})`;
      if (isObject) return `Object(${Object.keys(value).length})`;

      return String(value);
    };

    return (
      <div
        key={path}
        className={cn(
          "font-mono text-sm",
          depth > 0 && "ml-4 pl-2 border-l border-border",
        )}
      >
        <div className="flex items-center py-1 hover:bg-muted/50 rounded">
          {hasChildren ? (
            <Button
              variant="ghost"
              size="icon"
              className="h-5 w-5"
              onClick={() => toggleExpand(path)}
            >
              {isExpanded ? (
                <ChevronDown className="h-3 w-3" />
              ) : (
                <ChevronRight className="h-3 w-3" />
              )}
            </Button>
          ) : (
            <div className="w-5" />
          )}

          <div className="flex-1 flex items-center">
            <span className="font-medium mr-2">{path.split(".").pop()}:</span>
            <span className="text-muted-foreground">{getValueDisplay()}</span>
          </div>

          <div className="flex items-center gap-1">
            {typeof value === "string" && (
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6"
                onClick={() => toggleHideValue(path)}
              >
                {isHidden ? (
                  <Eye className="h-3 w-3" />
                ) : (
                  <EyeOff className="h-3 w-3" />
                )}
              </Button>
            )}
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6"
              onClick={() => copyToClipboard(value)}
            >
              <Copy className="h-3 w-3" />
            </Button>
          </div>
        </div>

        {isExpanded && hasChildren && (
          <div>
            {isObject &&
              Object.entries(value).map(([key, val], idx, arr) => (
                <React.Fragment key={`${path}.${key}`}>
                  {renderTreeValue(
                    val,
                    `${path}.${key}`,
                    depth + 1,
                    idx === arr.length - 1,
                  )}
                </React.Fragment>
              ))}
            {isArray &&
              value.map((val: any, idx: number, arr: any[]) => (
                <React.Fragment key={`${path}[${idx}]`}>
                  {renderTreeValue(
                    val,
                    `${path}[${idx}]`,
                    depth + 1,
                    idx === arr.length - 1,
                  )}
                </React.Fragment>
              ))}
          </div>
        )}
      </div>
    );
  };

  const renderTable = () => {
    // Flatten object for table view
    const flattenObject = (obj: any, prefix = ""): Record<string, any> => {
      return Object.keys(obj).reduce(
        (acc, key) => {
          const pre = prefix.length ? `${prefix}.` : "";
          if (
            typeof obj[key] === "object" &&
            obj[key] !== null &&
            !Array.isArray(obj[key])
          ) {
            Object.assign(acc, flattenObject(obj[key], `${pre}${key}`));
          } else {
            acc[`${pre}${key}`] = obj[key];
          }
          return acc;
        },
        {} as Record<string, any>,
      );
    };

    const flatVariables = flattenObject(filteredVariables);

    return (
      <div className="border rounded-md overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="bg-muted">
              <th className="text-left p-2 font-medium text-sm">Variable</th>
              <th className="text-left p-2 font-medium text-sm">Value</th>
              <th className="text-left p-2 font-medium text-sm w-10">
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(flatVariables).map(([key, value]) => (
              <tr key={key} className="border-t border-border">
                <td className="p-2 font-mono text-sm">{key}</td>
                <td className="p-2 font-mono text-sm text-muted-foreground">
                  {hiddenValues.includes(key)
                    ? "••••••••"
                    : typeof value === "object"
                      ? JSON.stringify(value)
                      : String(value)}
                </td>
                <td className="p-2">
                  <div className="flex items-center">
                    {typeof value === "string" && (
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6"
                        onClick={() => toggleHideValue(key)}
                      >
                        {hiddenValues.includes(key) ? (
                          <Eye className="h-3 w-3" />
                        ) : (
                          <EyeOff className="h-3 w-3" />
                        )}
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6"
                      onClick={() => copyToClipboard(value)}
                    >
                      <Copy className="h-3 w-3" />
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
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
          <div className="space-y-1">
            {Object.entries(filteredVariables).map(([key, value]) => (
              <React.Fragment key={key}>
                {renderTreeValue(value, key)}
              </React.Fragment>
            ))}
          </div>
        ) : viewType === "json" ? (
          <pre className="font-mono text-sm whitespace-pre-wrap">
            {JSON.stringify(filteredVariables, null, 2)}
          </pre>
        ) : (
          renderTable()
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
