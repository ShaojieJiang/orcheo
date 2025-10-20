import React, { useMemo, useState } from "react";
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
import type { WorkflowVersionRecord } from "@features/workflow/lib/workflow-persistence";
import {
  diffWorkflowSnapshots,
  type WorkflowDiffResult,
} from "@features/workflow/lib/workflow-diff";

type WorkflowVersion = WorkflowVersionRecord;

interface WorkflowHistoryProps {
  versions?: WorkflowVersionRecord[];
  currentVersion?: string;
  onSelectVersion?: (version: string) => void;
  onRestoreVersion?: (version: string) => void;
  className?: string;
}

export default function WorkflowHistory({
  versions = [],
  currentVersion,
  onSelectVersion,
  onRestoreVersion,
  className,
}: WorkflowHistoryProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedVersion, setSelectedVersion] = useState<string | null>(
    currentVersion || null,
  );
  const [compareVersion, setCompareVersion] = useState<string | null>(null);
  const [showDiffDialog, setShowDiffDialog] = useState(false);
  const [diffResult, setDiffResult] = useState<WorkflowDiffResult | null>(null);

  const filteredVersions = useMemo(() => {
    if (!searchQuery) {
      return versions;
    }

    const normalized = searchQuery.toLowerCase();
    return versions.filter((version) => {
      const versionMatch = version.version.toLowerCase().includes(normalized);
      const messageMatch = version.message?.toLowerCase().includes(normalized);
      const authorMatch = version.author?.name
        .toLowerCase()
        .includes(normalized);
      return versionMatch || messageMatch || authorMatch;
    });
  }, [searchQuery, versions]);

  const handleSelectVersion = (version: string) => {
    setSelectedVersion(version);
    onSelectVersion?.(version);
  };

  const handleCompareVersions = () => {
    if (!selectedVersion || !compareVersion) {
      return;
    }

    const baseVersion = versions.find((v) => v.version === selectedVersion);
    const targetVersion = versions.find((v) => v.version === compareVersion);

    if (!baseVersion || !targetVersion) {
      return;
    }

    setDiffResult(
      diffWorkflowSnapshots(
        baseVersion.nodes,
        baseVersion.edges,
        targetVersion.nodes,
        targetVersion.edges,
      ),
    );
    setShowDiffDialog(true);
  };

  const handleRestoreVersion = () => {
    if (selectedVersion) {
      onRestoreVersion?.(selectedVersion);
    }
  };

  const handleExportDiff = () => {
    if (!diffResult || !selectedVersion || !compareVersion) {
      return;
    }

    const diffPayload = {
      baseVersion: selectedVersion,
      compareVersion,
      diff: diffResult,
    };

    const blob = new Blob([JSON.stringify(diffPayload, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `workflow-diff-${selectedVersion}-vs-${compareVersion}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const getStatusBadge = (version: WorkflowVersion) => {
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
            disabled={!selectedVersion || selectedVersion === currentVersion}
          >
            <RotateCcw className="h-4 w-4 mr-2" />
            Restore
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleCompareVersions}
            disabled={!selectedVersion || !compareVersion}
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
        <Select value={compareVersion || ""} onValueChange={setCompareVersion}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Compare with..." />
          </SelectTrigger>
          <SelectContent>
            {versions
              .filter((v) => v.version !== selectedVersion)
              .map((version) => (
                <SelectItem key={version.id} value={version.version}>
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
              filteredVersions.map((version) => (
                <TableRow
                  key={version.id}
                  className={cn(
                    "cursor-pointer",
                    selectedVersion === version.version && "bg-muted",
                  )}
                  onClick={() => handleSelectVersion(version.version)}
                >
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-2">
                      <GitCommit className="h-4 w-4 text-muted-foreground" />

                      {version.version}
                      {getStatusBadge(version)}
                    </div>
                  </TableCell>
                  <TableCell>
                    {version.message || "No summary provided"}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <div className="h-6 w-6 rounded-full overflow-hidden bg-muted">
                        <img
                          src={
                            version.author?.avatar ??
                            "https://avatar.vercel.sh/orcheo"
                          }
                          alt={version.author?.name ?? "Unknown"}
                          className="h-full w-full object-cover"
                        />
                      </div>
                      {version.author?.name ?? "Unknown"}
                    </div>
                  </TableCell>
                  <TableCell>
                    {new Date(version.timestamp).toLocaleString()}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-2">
                      {version.changes.added > 0 && (
                        <Badge className="bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400">
                          +{version.changes.added}
                        </Badge>
                      )}
                      {version.changes.removed > 0 && (
                        <Badge className="bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400">
                          -{version.changes.removed}
                        </Badge>
                      )}
                      {version.changes.modified > 0 && (
                        <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400">
                          ~{version.changes.modified}
                        </Badge>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))
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
      <Dialog
        open={showDiffDialog}
        onOpenChange={(open) => {
          setShowDiffDialog(open);
          if (!open) {
            setDiffResult(null);
          }
        }}
      >
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>Compare Versions</DialogTitle>
            <DialogDescription>
              Comparing {selectedVersion} with {compareVersion}
            </DialogDescription>
          </DialogHeader>

          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <GitBranch className="h-4 w-4" />

                <span className="font-medium">{selectedVersion}</span>
                <span className="text-muted-foreground">→</span>
                <GitBranch className="h-4 w-4" />

                <span className="font-medium">{compareVersion}</span>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={handleExportDiff}
                disabled={!diffResult}
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
                    Added
                  </Badge>
                  <Badge className="bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400">
                    Removed
                  </Badge>
                  <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400">
                    Modified
                  </Badge>
                </div>
              </div>

              <div className="p-4 bg-muted/20 space-y-6">
                {!diffResult ? (
                  <div className="text-sm text-muted-foreground">
                    Select two versions to generate a diff.
                  </div>
                ) : (
                  <>
                    <div>
                      <h4 className="text-sm font-semibold mb-2">
                        Node changes
                      </h4>
                      <div className="space-y-2">
                        {diffResult.nodes.added.map((node) => (
                          <div
                            key={`node-added-${node.id}`}
                            className="bg-green-100 dark:bg-green-900/20 p-2 rounded text-sm"
                          >
                            + Added node "{node.label}"
                          </div>
                        ))}
                        {diffResult.nodes.removed.map((node) => (
                          <div
                            key={`node-removed-${node.id}`}
                            className="bg-red-100 dark:bg-red-900/20 p-2 rounded text-sm"
                          >
                            − Removed node "{node.label}"
                          </div>
                        ))}
                        {diffResult.nodes.modified.map((node) => (
                          <div
                            key={`node-modified-${node.id}`}
                            className="bg-blue-100 dark:bg-blue-900/20 p-2 rounded text-sm space-y-2"
                          >
                            <div className="font-medium">
                              ~ Updated node "{node.label}"
                            </div>
                            <div className="grid gap-2 md:grid-cols-2 text-xs font-mono">
                              <div className="bg-background/80 p-2 rounded">
                                <div className="text-muted-foreground mb-1">
                                  Before
                                </div>
                                <pre className="whitespace-pre-wrap break-words">
                                  {JSON.stringify(node.before?.data, null, 2)}
                                </pre>
                              </div>
                              <div className="bg-background/80 p-2 rounded">
                                <div className="text-muted-foreground mb-1">
                                  After
                                </div>
                                <pre className="whitespace-pre-wrap break-words">
                                  {JSON.stringify(node.after?.data, null, 2)}
                                </pre>
                              </div>
                            </div>
                          </div>
                        ))}
                        {diffResult.nodes.added.length === 0 &&
                          diffResult.nodes.removed.length === 0 &&
                          diffResult.nodes.modified.length === 0 && (
                            <div className="text-sm text-muted-foreground">
                              No node changes detected.
                            </div>
                          )}
                      </div>
                    </div>

                    <div>
                      <h4 className="text-sm font-semibold mb-2">
                        Edge changes
                      </h4>
                      <div className="space-y-2">
                        {diffResult.edges.added.map((edge) => (
                          <div
                            key={`edge-added-${edge.id}`}
                            className="bg-green-100 dark:bg-green-900/20 p-2 rounded text-sm"
                          >
                            + Added edge {edge.after?.source} →{" "}
                            {edge.after?.target}
                          </div>
                        ))}
                        {diffResult.edges.removed.map((edge) => (
                          <div
                            key={`edge-removed-${edge.id}`}
                            className="bg-red-100 dark:bg-red-900/20 p-2 rounded text-sm"
                          >
                            − Removed edge {edge.before?.source} →{" "}
                            {edge.before?.target}
                          </div>
                        ))}
                        {diffResult.edges.modified.map((edge) => (
                          <div
                            key={`edge-modified-${edge.id}`}
                            className="bg-blue-100 dark:bg-blue-900/20 p-2 rounded text-sm space-y-2"
                          >
                            <div className="font-medium">
                              ~ Updated edge {edge.before?.source} →{" "}
                              {edge.before?.target}
                            </div>
                            <div className="grid gap-2 md:grid-cols-2 text-xs font-mono">
                              <div className="bg-background/80 p-2 rounded">
                                <div className="text-muted-foreground mb-1">
                                  Before
                                </div>
                                <pre className="whitespace-pre-wrap break-words">
                                  {JSON.stringify(edge.before, null, 2)}
                                </pre>
                              </div>
                              <div className="bg-background/80 p-2 rounded">
                                <div className="text-muted-foreground mb-1">
                                  After
                                </div>
                                <pre className="whitespace-pre-wrap break-words">
                                  {JSON.stringify(edge.after, null, 2)}
                                </pre>
                              </div>
                            </div>
                          </div>
                        ))}
                        {diffResult.edges.added.length === 0 &&
                          diffResult.edges.removed.length === 0 &&
                          diffResult.edges.modified.length === 0 && (
                            <div className="text-sm text-muted-foreground">
                              No edge changes detected.
                            </div>
                          )}
                      </div>
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
