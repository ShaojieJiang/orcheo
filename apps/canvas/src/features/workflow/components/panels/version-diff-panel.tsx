import React, { useMemo, useState } from "react";
import { Button } from "@/design-system/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/design-system/ui/card";
import { Label } from "@/design-system/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/design-system/ui/select";
import { Badge } from "@/design-system/ui/badge";
import { ScrollArea } from "@/design-system/ui/scroll-area";
import { ArrowLeftRight, Download, GitBranch, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export interface VersionSummary {
  id: string;
  version: number;
  createdAt: string;
  createdBy: string;
  notes?: string | null;
}

interface VersionDiffPanelProps {
  workflowName: string;
  versions: VersionSummary[];
  diffLines: string[];
  isLoadingDiff: boolean;
  onCompare: (baseVersion: number, targetVersion: number) => Promise<void>;
}

const DEFAULT_DIFF_MESSAGE = "Select two versions to see the graph diff.";

export function VersionDiffPanel({
  workflowName,
  versions,
  diffLines,
  isLoadingDiff,
  onCompare,
}: VersionDiffPanelProps) {
  const sortedVersions = useMemo(
    () => [...versions].sort((a, b) => b.version - a.version),
    [versions],
  );

  const [baseVersion, setBaseVersion] = useState<number | undefined>(
    sortedVersions[1]?.version,
  );
  const [targetVersion, setTargetVersion] = useState<number | undefined>(
    sortedVersions[0]?.version,
  );
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCompare = async () => {
    if (baseVersion === undefined || targetVersion === undefined) {
      setError("Select both base and target versions to compare.");
      return;
    }
    if (baseVersion === targetVersion) {
      setError("Choose two different versions to generate a diff.");
      return;
    }
    setError(null);
    await onCompare(baseVersion, targetVersion);
  };

  const handleExportDiff = () => {
    setIsExporting(true);
    try {
      const text = diffLines.length > 0 ? diffLines.join("\n") : "(no changes)";
      const blob = new Blob([text], { type: "text/plain" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${workflowName.replace(/\s+/g, "-").toLowerCase() || "workflow"}-diff.txt`;
      anchor.click();
      URL.revokeObjectURL(url);
    } finally {
      setIsExporting(false);
    }
  };

  const renderDiffLine = (line: string, index: number) => {
    const trimmed = line.trimStart();
    if (trimmed.startsWith("+++")) {
      return null;
    }
    if (trimmed.startsWith("---")) {
      return null;
    }
    const firstChar = trimmed.charAt(0);
    const className = cn(
      "font-mono text-sm px-3 py-1 rounded-md border",
      firstChar === "+" &&
        "bg-emerald-500/10 border-emerald-500/20 text-emerald-600 dark:text-emerald-300",
      firstChar === "-" &&
        "bg-destructive/10 border-destructive/20 text-destructive",
      firstChar !== "+" &&
        firstChar !== "-" &&
        "bg-muted border-border text-muted-foreground",
    );
    return (
      <div key={`${index}-${line}`} className={className}>
        {line}
      </div>
    );
  };

  return (
    <Card className="h-full flex flex-col">
      <CardHeader className="space-y-4">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <GitBranch className="h-5 w-5" />
            Version history
          </CardTitle>
          <Badge variant="secondary">{versions.length} versions</Badge>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="base-version">Base version</Label>
            <Select
              value={baseVersion?.toString() ?? ""}
              onValueChange={(value) => setBaseVersion(Number(value))}
            >
              <SelectTrigger id="base-version">
                <SelectValue placeholder="Select version" />
              </SelectTrigger>
              <SelectContent>
                {sortedVersions.map((version) => (
                  <SelectItem
                    key={version.id}
                    value={version.version.toString()}
                  >
                    v{version.version} ·{" "}
                    {new Date(version.createdAt).toLocaleString()}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="target-version">Target version</Label>
            <Select
              value={targetVersion?.toString() ?? ""}
              onValueChange={(value) => setTargetVersion(Number(value))}
            >
              <SelectTrigger id="target-version">
                <SelectValue placeholder="Select version" />
              </SelectTrigger>
              <SelectContent>
                {sortedVersions.map((version) => (
                  <SelectItem
                    key={version.id}
                    value={version.version.toString()}
                  >
                    v{version.version} ·{" "}
                    {new Date(version.createdAt).toLocaleString()}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button onClick={handleCompare} disabled={isLoadingDiff}>
            {isLoadingDiff ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <ArrowLeftRight className="mr-2 h-4 w-4" />
            )}
            Compare versions
          </Button>
          <Button
            variant="outline"
            onClick={handleExportDiff}
            disabled={diffLines.length === 0 || isExporting}
          >
            {isExporting ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Download className="mr-2 h-4 w-4" />
            )}
            Export diff
          </Button>
          {error && <span className="text-sm text-destructive">{error}</span>}
        </div>
      </CardHeader>
      <CardContent className="flex-1">
        <ScrollArea className="h-full">
          <div className="space-y-2">
            {diffLines.length === 0 ? (
              <div className="text-muted-foreground text-sm py-6 text-center">
                {DEFAULT_DIFF_MESSAGE}
              </div>
            ) : (
              diffLines.map(renderDiffLine)
            )}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
