import React, { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/design-system/ui/dialog";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/design-system/ui/tabs";
import { Input } from "@/design-system/ui/input";
import { Button } from "@/design-system/ui/button";
import { Label } from "@/design-system/ui/label";
import { Textarea } from "@/design-system/ui/textarea";
import { Badge } from "@/design-system/ui/badge";
import { Save, Download, Upload, Copy, GitBranch } from "lucide-react";

interface VersionControlDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSave?: (version: string, description: string) => void;
  onDuplicate?: () => void;
  onExport?: () => void;
  onImport?: (jsonData: string) => void;
  currentVersion?: string;
}

export default function VersionControlDialog({
  open,
  onOpenChange,
  onSave,
  onDuplicate,
  onExport,
  onImport,
  currentVersion = "1.0.0",
}: VersionControlDialogProps) {
  const [activeTab, setActiveTab] = useState("save");
  const [version, setVersion] = useState(currentVersion);
  const [description, setDescription] = useState("");
  const [importData, setImportData] = useState("");
  const [importError, setImportError] = useState("");

  const handleSave = () => {
    if (onSave) {
      onSave(version, description);
    }
    onOpenChange(false);
  };

  const handleImport = () => {
    try {
      // Basic validation to check if it's valid JSON
      JSON.parse(importData);
      setImportError("");
      if (onImport) {
        onImport(importData);
      }
      onOpenChange(false);
    } catch {
      setImportError("Invalid JSON format");
    }
  };

  const handleExport = () => {
    if (onExport) {
      onExport();
    }
    onOpenChange(false);
  };

  const handleDuplicate = () => {
    if (onDuplicate) {
      onDuplicate();
    }
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Workflow Version Control</DialogTitle>
        </DialogHeader>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid grid-cols-4 mb-4">
            <TabsTrigger value="save" className="flex items-center gap-2">
              <Save className="h-4 w-4" />

              <span className="hidden sm:inline">Save</span>
            </TabsTrigger>
            <TabsTrigger value="duplicate" className="flex items-center gap-2">
              <Copy className="h-4 w-4" />

              <span className="hidden sm:inline">Duplicate</span>
            </TabsTrigger>
            <TabsTrigger value="export" className="flex items-center gap-2">
              <Download className="h-4 w-4" />

              <span className="hidden sm:inline">Export</span>
            </TabsTrigger>
            <TabsTrigger value="import" className="flex items-center gap-2">
              <Upload className="h-4 w-4" />

              <span className="hidden sm:inline">Import</span>
            </TabsTrigger>
          </TabsList>

          <TabsContent value="save" className="space-y-4">
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <GitBranch className="h-4 w-4 text-muted-foreground" />

                <Label htmlFor="version">Version</Label>
                <Badge variant="outline" className="ml-auto">
                  Current: {currentVersion}
                </Badge>
              </div>
              <Input
                id="version"
                value={version}
                onChange={(e) => setVersion(e.target.value)}
                placeholder="1.0.0"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe your changes..."
                rows={4}
              />
            </div>
            <DialogFooter className="sm:justify-end">
              <Button
                type="button"
                variant="secondary"
                onClick={() => onOpenChange(false)}
              >
                Cancel
              </Button>
              <Button type="button" onClick={handleSave}>
                Save Version
              </Button>
            </DialogFooter>
          </TabsContent>

          <TabsContent value="duplicate" className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Create a duplicate copy of this workflow. The new workflow will be
              added to your workspace with "(Copy)" appended to its name.
            </p>
            <DialogFooter className="sm:justify-end">
              <Button
                type="button"
                variant="secondary"
                onClick={() => onOpenChange(false)}
              >
                Cancel
              </Button>
              <Button type="button" onClick={handleDuplicate}>
                Duplicate Workflow
              </Button>
            </DialogFooter>
          </TabsContent>

          <TabsContent value="export" className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Export this workflow as a JSON file. You can import it later or
              share it with others.
            </p>
            <DialogFooter className="sm:justify-end">
              <Button
                type="button"
                variant="secondary"
                onClick={() => onOpenChange(false)}
              >
                Cancel
              </Button>
              <Button type="button" onClick={handleExport}>
                Export JSON
              </Button>
            </DialogFooter>
          </TabsContent>

          <TabsContent value="import" className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="import-data">Paste JSON Data</Label>
              <Textarea
                id="import-data"
                value={importData}
                onChange={(e) => {
                  setImportData(e.target.value);
                  setImportError("");
                }}
                placeholder="Paste your workflow JSON here..."
                rows={6}
                className={importError ? "border-red-500" : ""}
              />

              {importError && (
                <p className="text-sm text-red-500">{importError}</p>
              )}
            </div>
            <DialogFooter className="sm:justify-end">
              <Button
                type="button"
                variant="secondary"
                onClick={() => onOpenChange(false)}
              >
                Cancel
              </Button>
              <Button
                type="button"
                onClick={handleImport}
                disabled={!importData}
              >
                Import
              </Button>
            </DialogFooter>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
