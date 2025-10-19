import React, { useState } from "react";
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

interface WorkflowVersion {
  id: string;
  version: string;
  timestamp: string;
  author: {
    name: string;
    avatar: string;
  };
  message: string;
  changes: {
    added: number;
    removed: number;
    modified: number;
  };
}

interface WorkflowHistoryProps {
  versions?: WorkflowVersion[];
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

  // Filter versions based on search query
  const filteredVersions = searchQuery
    ? versions.filter(
        (version) =>
          version.version.includes(searchQuery) ||
          version.message.toLowerCase().includes(searchQuery.toLowerCase()) ||
          version.author.name.toLowerCase().includes(searchQuery.toLowerCase()),
      )
    : versions;

  const handleSelectVersion = (version: string) => {
    setSelectedVersion(version);
    onSelectVersion?.(version);
  };

  const handleCompareVersions = () => {
    if (selectedVersion && compareVersion) {
      setShowDiffDialog(true);
    }
  };

  const handleRestoreVersion = () => {
    if (selectedVersion) {
      onRestoreVersion?.(selectedVersion);
    }
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
      <Dialog open={showDiffDialog} onOpenChange={setShowDiffDialog}>
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
              <Button variant="outline" size="sm">
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

              <div className="p-4 bg-muted/20">
                <div className="space-y-4">
                  {/* Sample diff visualization */}
                  <div className="border rounded-md overflow-hidden">
                    <div className="bg-muted p-2 border-b border-border">
                      <span className="font-medium">HTTP Request Node</span>
                    </div>
                    <div className="p-2">
                      <div className="bg-green-100 dark:bg-green-900/20 p-1 rounded text-sm font-mono">
                        + "url": "https://api.example.com/v2/data"
                      </div>
                      <div className="bg-red-100 dark:bg-red-900/20 p-1 rounded text-sm font-mono">
                        - "url": "https://api.example.com/v1/data"
                      </div>
                    </div>
                  </div>

                  <div className="border rounded-md overflow-hidden">
                    <div className="bg-muted p-2 border-b border-border">
                      <span className="font-medium">Transform Data Node</span>
                    </div>
                    <div className="p-2">
                      <div className="bg-blue-100 dark:bg-blue-900/20 p-1 rounded text-sm font-mono">
                        ~ "expression": "data.items[?value {">"} `200`]"
                      </div>
                      <div className="bg-blue-100 dark:bg-blue-900/20 p-1 rounded text-sm font-mono">
                        ~ "expression": "data.items[?value {">"} `100`]"
                      </div>
                    </div>
                  </div>

                  <div className="border rounded-md overflow-hidden">
                    <div className="bg-muted p-2 border-b border-border">
                      <span className="font-medium">Send Email Node</span>
                    </div>
                    <div className="p-2">
                      <div className="bg-green-100 dark:bg-green-900/20 p-1 rounded text-sm font-mono">
                        + Added new node
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
