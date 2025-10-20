import React, { useEffect, useMemo, useState } from "react";
import { Button } from "@/design-system/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/design-system/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/design-system/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/design-system/ui/select";
import { Input } from "@/design-system/ui/input";
import { Badge } from "@/design-system/ui/badge";
import { ScrollArea } from "@/design-system/ui/scroll-area";
import {
  History,
  Search,
  ChevronLeft,
  ChevronRight,
  GitCommit,
  GitBranch,
  RotateCcw,
  FileDown,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { computeWorkflowDiff } from "@features/workflow/lib/workflow-diff";
import type { WorkflowVersionRecord } from "@features/workflow/lib/workflow-storage";

interface WorkflowHistoryProps {
  versions?: WorkflowVersionRecord[];
  currentVersion?: string;
  onRestoreVersion?: (versionId: string) => void;
  className?: string;
}

export default function WorkflowHistory({
  versions = [],
  currentVersion,
  onRestoreVersion,
  className,
}: WorkflowHistoryProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(
    null,
  );
  const [compareVersionId, setCompareVersionId] = useState<string | null>(null);
  const [showDiffDialog, setShowDiffDialog] = useState(false);
  const [diffContext, setDiffContext] = useState<{
    base: WorkflowVersionRecord;
    target: WorkflowVersionRecord;
    result: ReturnType<typeof computeWorkflowDiff>;
  } | null>(null);

  useEffect(() => {
    if (!versions.length) {
      setSelectedVersionId(null);
      setCompareVersionId(null);
      return;
    }

    if (currentVersion) {
      const matched = versions.find(
        (version) => version.version === currentVersion,
      );
      setSelectedVersionId(matched?.id ?? null);
    } else if (!selectedVersionId) {
      setSelectedVersionId(versions[0].id);
    }
  }, [currentVersion, selectedVersionId, versions]);

  // Filter versions based on search query
  const filteredVersions = useMemo(() => {
    if (!searchQuery) {
      return versions;
    }
    return versions.filter(
      (version) =>
        version.version.toLowerCase().includes(searchQuery.toLowerCase()) ||
        version.message.toLowerCase().includes(searchQuery.toLowerCase()) ||
        version.author.name.toLowerCase().includes(searchQuery.toLowerCase()),
    );
  }, [searchQuery, versions]);

  const selectedVersionRecord = useMemo(() => {
    return versions.find((version) => version.id === selectedVersionId) ?? null;
  }, [selectedVersionId, versions]);

  const compareVersionRecord = useMemo(() => {
    return versions.find((version) => version.id === compareVersionId) ?? null;
  }, [compareVersionId, versions]);

  const handleSelectVersion = (versionId: string) => {
    setSelectedVersionId(versionId);
    if (compareVersionId === versionId) {
      setCompareVersionId(null);
    }
  };

  const handleCompareVersions = () => {
    if (!selectedVersionRecord || !compareVersionRecord) {
      return;
    }
    const diffResult = computeWorkflowDiff(
      selectedVersionRecord.snapshot,
      compareVersionRecord.snapshot,
    );
    setDiffContext({
      base: selectedVersionRecord,
      target: compareVersionRecord,
      result: diffResult,
    });
    setShowDiffDialog(true);
  };

  const handleRestoreVersion = () => {
    if (selectedVersionId) {
      onRestoreVersion?.(selectedVersionId);
    }
  };

  const getStatusBadge = (version: WorkflowVersionRecord) => {
    if (version.version === currentVersion) {
      return (
        <Badge className="bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400">
          Current
        </Badge>
      );
    }
    return null;
  };

  return (
    <div
      className={cn(
        "flex flex-col border border-border rounded-lg bg-background shadow-lg",
        className,
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border">
        <div className="flex items-center gap-2">
          <History className="h-5 w-5" />

          <h3 className="font-medium">Version History</h3>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleRestoreVersion}
            disabled={
              !selectedVersionRecord ||
              (currentVersion &&
                selectedVersionRecord.version === currentVersion)
            }
          >
            <RotateCcw className="h-4 w-4 mr-2" />
            Restore
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleCompareVersions}
            disabled={!selectedVersionRecord || !compareVersionRecord}
          >
            Compare
          </Button>
        </div>
      </div>

      {/* Search and filter */}
      <div className="flex items-center gap-2 p-4 border-b border-border">
        <div className="relative flex-1">
          <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />

          <Input
            placeholder="Search versions..."
            className="pl-8"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
        <Select
          value={compareVersionId ?? ""}
          onValueChange={(value) => setCompareVersionId(value || null)}
        >
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Compare with..." />
          </SelectTrigger>
          <SelectContent>
            {versions
              .filter((version) => version.id !== selectedVersionId)
              .map((version) => (
                <SelectItem key={version.id} value={version.id}>
                  {version.version}
                </SelectItem>
              ))}
          </SelectContent>
        </Select>
      </div>

      {/* Versions list */}
      <ScrollArea className="flex-1 h-[400px]">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[100px]">Version</TableHead>
              <TableHead>Message</TableHead>
              <TableHead>Author</TableHead>
              <TableHead>Date</TableHead>
              <TableHead className="text-right">Changes</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredVersions.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center py-8">
                  <div className="text-muted-foreground">
                    No versions found
                    {searchQuery && (
                      <p className="text-sm">Try adjusting your search query</p>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              filteredVersions.map((version) => {
                const isSelected = selectedVersionId === version.id;
                return (
                  <TableRow
                    key={version.id}
                    className={cn("cursor-pointer", isSelected && "bg-muted")}
                    onClick={() => handleSelectVersion(version.id)}
                  >
                    <TableCell className="font-medium">
                      <div className="flex items-center gap-2">
                        <GitCommit className="h-4 w-4 text-muted-foreground" />

                        {version.version}
                        {getStatusBadge(version)}
                      </div>
                    </TableCell>
                    <TableCell>{version.message}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <div className="h-6 w-6 rounded-full overflow-hidden bg-muted">
                          <img
                            src={version.author.avatar}
                            alt={version.author.name}
                            className="h-full w-full object-cover"
                          />
                        </div>
                        {version.author.name}
                      </div>
                    </TableCell>
                    <TableCell>
                      {new Date(version.timestamp).toLocaleString()}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        {version.summary.added > 0 && (
                          <Badge className="bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400">
                            +{version.summary.added}
                          </Badge>
                        )}
                        {version.summary.removed > 0 && (
                          <Badge className="bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400">
                            -{version.summary.removed}
                          </Badge>
                        )}
                        {version.summary.modified > 0 && (
                          <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400">
                            ~{version.summary.modified}
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </ScrollArea>

      {/* Footer */}
      <div className="flex items-center justify-between p-4 border-t border-border">
        <div className="text-sm text-muted-foreground">
          {filteredVersions.length} versions
        </div>
        <div className="flex items-center gap-1">
          <Button variant="outline" size="icon" className="h-8 w-8">
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button variant="outline" size="icon" className="h-8 w-8">
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Diff Dialog */}
      <Dialog open={showDiffDialog} onOpenChange={setShowDiffDialog}>
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>Compare Versions</DialogTitle>
            <DialogDescription>
              {diffContext
                ? `Comparing ${diffContext.base.version} with ${diffContext.target.version}`
                : "Select two versions to compare."}
            </DialogDescription>
          </DialogHeader>

          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <GitBranch className="h-4 w-4" />

                <span className="font-medium">
                  {diffContext?.base.version ??
                    selectedVersionRecord?.version ??
                    "Select a version"}
                </span>
                <span className="text-muted-foreground">→</span>
                <GitBranch className="h-4 w-4" />

                <span className="font-medium">
                  {diffContext?.target.version ??
                    compareVersionRecord?.version ??
                    "Select a version"}
                </span>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  if (!diffContext) {
                    return;
                  }
                  const payload = {
                    baseVersion: diffContext.base.version,
                    targetVersion: diffContext.target.version,
                    summary: diffContext.result.summary,
                    entries: diffContext.result.entries,
                  };
                  const serialized = JSON.stringify(payload, null, 2);
                  const blob = new Blob([serialized], {
                    type: "application/json",
                  });
                  const url = URL.createObjectURL(blob);
                  const anchor = document.createElement("a");
                  anchor.href = url;
                  anchor.download = `workflow-diff-${diffContext.base.version}-vs-${diffContext.target.version}.json`;
                  anchor.click();
                  URL.revokeObjectURL(url);
                }}
                disabled={!diffContext}
              >
                <FileDown className="h-4 w-4 mr-2" />
                Export Diff
              </Button>
            </div>

            <div className="border rounded-md overflow-hidden">
              <div className="bg-muted p-2 border-b border-border flex items-center justify-between">
                <div className="text-sm font-medium">Changes</div>
                <div className="flex items-center gap-2">
                  <Badge className="bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400">
                    Added {diffContext?.result.summary.added ?? 0}
                  </Badge>
                  <Badge className="bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400">
                    Removed {diffContext?.result.summary.removed ?? 0}
                  </Badge>
                  <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400">
                    Modified {diffContext?.result.summary.modified ?? 0}
                  </Badge>
                </div>
              </div>

              <div className="p-4 bg-muted/20">
                <div className="space-y-4">
                  {diffContext && diffContext.result.entries.length > 0 ? (
                    diffContext.result.entries.map((entry) => {
                      const badgeClass =
                        entry.type === "added"
                          ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400"
                          : entry.type === "removed"
                            ? "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400"
                            : "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400";

                      const formatValue = (value: unknown) =>
                        typeof value === "string" ||
                        typeof value === "number" ||
                        typeof value === "boolean"
                          ? value.toString()
                          : JSON.stringify(value, null, 2);

                      return (
                        <div
                          key={entry.id}
                          className="border rounded-md overflow-hidden"
                        >
                          <div className="bg-muted p-2 border-b border-border flex items-center justify-between">
                            <div>
                              <span className="font-medium">{entry.name}</span>
                              <span className="ml-2 text-xs uppercase text-muted-foreground">
                                {entry.entity}
                              </span>
                            </div>
                            <Badge className={badgeClass}>{entry.type}</Badge>
                          </div>
                          <div className="p-3 space-y-2 text-sm">
                            {entry.detail && (
                              <p className="text-muted-foreground">
                                {entry.detail}
                              </p>
                            )}
                            {entry.type !== "added" &&
                              entry.before !== undefined && (
                                <pre className="bg-red-50 dark:bg-red-900/20 rounded-md p-2 font-mono text-xs whitespace-pre-wrap">
                                  - {formatValue(entry.before)}
                                </pre>
                              )}
                            {entry.type !== "removed" &&
                              entry.after !== undefined && (
                                <pre className="bg-green-50 dark:bg-green-900/20 rounded-md p-2 font-mono text-xs whitespace-pre-wrap">
                                  + {formatValue(entry.after)}
                                </pre>
                              )}
                          </div>
                        </div>
                      );
                    })
                  ) : (
                    <div className="text-sm text-muted-foreground">
                      No differences detected between the selected versions.
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
