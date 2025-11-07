"use client";

import React from "react";
import { Button } from "@/design-system/ui/button";
import { Copy, Eye, EyeOff } from "lucide-react";
import type { VariablesMap } from "./variable-inspector-types";

interface VariableTableViewProps {
  variables: VariablesMap;
  hiddenValues: string[];
  onToggleHideValue: (path: string) => void;
  onCopy: (value: unknown) => void;
}

export function VariableTableView({
  variables,
  hiddenValues,
  onToggleHideValue,
  onCopy,
}: VariableTableViewProps) {
  const flatVariables = React.useMemo(
    () => flattenObject(variables),
    [variables],
  );

  return (
    <div className="border rounded-md overflow-hidden">
      <table className="w-full">
        <thead>
          <tr className="bg-muted">
            <th className="text-left p-2 font-medium text-sm">Variable</th>
            <th className="text-left p-2 font-medium text-sm">Value</th>
            <th className="text-left p-2 font-medium text-sm w-10">Actions</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(flatVariables).map(([key, value]) => {
            const isHidden = hiddenValues.includes(key);
            const displayValue =
              isHidden && typeof value === "string"
                ? "••••••••"
                : typeof value === "object"
                  ? JSON.stringify(value)
                  : String(value);

            return (
              <tr key={key} className="border-t border-border">
                <td className="p-2 font-mono text-sm">{key}</td>
                <td className="p-2 font-mono text-sm text-muted-foreground">
                  {displayValue}
                </td>
                <td className="p-2">
                  <div className="flex items-center">
                    {typeof value === "string" && (
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6"
                        onClick={() => onToggleHideValue(key)}
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
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

const flattenObject = (obj: VariablesMap, prefix = ""): VariablesMap => {
  return Object.entries(obj).reduce<VariablesMap>((acc, [key, value]) => {
    const pre = prefix.length ? `${prefix}.` : "";

    if (value !== null && typeof value === "object" && !Array.isArray(value)) {
      Object.assign(acc, flattenObject(value as VariablesMap, `${pre}${key}`));
      return acc;
    }

    acc[`${pre}${key}`] = value;
    return acc;
  }, {});
};
