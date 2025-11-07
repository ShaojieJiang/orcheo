"use client";

import React from "react";
import { Button } from "@/design-system/ui/button";
import { Copy, Eye, EyeOff, ChevronRight, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import type { VariablesMap } from "./variable-inspector-types";

interface VariableTreeViewProps {
  variables: VariablesMap;
  expandedPaths: string[];
  hiddenValues: string[];
  onToggleExpand: (path: string) => void;
  onToggleHideValue: (path: string) => void;
  onCopy: (value: unknown) => void;
}

export function VariableTreeView({
  variables,
  expandedPaths,
  hiddenValues,
  onToggleExpand,
  onToggleHideValue,
  onCopy,
}: VariableTreeViewProps) {
  return (
    <div className="space-y-1">
      {Object.entries(variables).map(([key, value]) => (
        <TreeValue
          key={key}
          path={key}
          value={value}
          expandedPaths={expandedPaths}
          hiddenValues={hiddenValues}
          onToggleExpand={onToggleExpand}
          onToggleHideValue={onToggleHideValue}
          onCopy={onCopy}
        />
      ))}
    </div>
  );
}

interface TreeValueProps {
  value: unknown;
  path: string;
  expandedPaths: string[];
  hiddenValues: string[];
  onToggleExpand: (path: string) => void;
  onToggleHideValue: (path: string) => void;
  onCopy: (value: unknown) => void;
  depth?: number;
}

function TreeValue({
  value,
  path,
  expandedPaths,
  hiddenValues,
  onToggleExpand,
  onToggleHideValue,
  onCopy,
  depth = 0,
}: TreeValueProps) {
  const isExpanded = expandedPaths.includes(path);
  const isHidden = hiddenValues.includes(path);
  const isObject =
    value !== null && typeof value === "object" && !Array.isArray(value);
  const isArray = Array.isArray(value);
  const hasChildren = isObject || isArray;
  const objectValue = isObject ? (value as VariablesMap) : undefined;
  const arrayValue = isArray ? (value as unknown[]) : undefined;

  const renderValue = () => {
    if (isHidden) return "••••••••";

    if (value === null)
      return <span className="text-muted-foreground">null</span>;

    if (value === undefined)
      return <span className="text-muted-foreground">undefined</span>;

    if (typeof value === "string") return `"${value}"`;
    if (typeof value === "number")
      return <span className="text-blue-500 dark:text-blue-400">{value}</span>;

    if (typeof value === "boolean")
      return (
        <span className="text-amber-500 dark:text-amber-400">
          {String(value)}
        </span>
      );

    if (isArray) return `Array(${arrayValue?.length ?? 0})`;
    if (isObject)
      return `Object(${objectValue ? Object.keys(objectValue).length : 0})`;

    return String(value);
  };

  const label = path.split(".").pop();

  return (
    <div
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
            onClick={() => onToggleExpand(path)}
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
          <span className="font-medium mr-2">{label}:</span>
          <span className="text-muted-foreground">{renderValue()}</span>
        </div>

        <div className="flex items-center gap-1">
          {typeof value === "string" && (
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6"
              onClick={() => onToggleHideValue(path)}
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
            onClick={() => onCopy(value)}
          >
            <Copy className="h-3 w-3" />
          </Button>
        </div>
      </div>

      {isExpanded && hasChildren && (
        <div>
          {isObject &&
            Object.entries(objectValue ?? {}).map(([key, val]) => (
              <TreeValue
                key={`${path}.${key}`}
                value={val}
                path={`${path}.${key}`}
                depth={depth + 1}
                expandedPaths={expandedPaths}
                hiddenValues={hiddenValues}
                onToggleExpand={onToggleExpand}
                onToggleHideValue={onToggleHideValue}
                onCopy={onCopy}
              />
            ))}
          {isArray &&
            (arrayValue ?? []).map((val, idx) => (
              <TreeValue
                key={`${path}[${idx}]`}
                value={val}
                path={`${path}[${idx}]`}
                depth={depth + 1}
                expandedPaths={expandedPaths}
                hiddenValues={hiddenValues}
                onToggleExpand={onToggleExpand}
                onToggleHideValue={onToggleHideValue}
                onCopy={onCopy}
              />
            ))}
        </div>
      )}
    </div>
  );
}
