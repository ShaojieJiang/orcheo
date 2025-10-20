import React, { useState, useRef } from "react";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/design-system/ui/tabs";
import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";
import { Label } from "@/design-system/ui/label";
import { Textarea } from "@/design-system/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/design-system/ui/select";
import { Switch } from "@/design-system/ui/switch";
import { ScrollArea } from "@/design-system/ui/scroll-area";
import { Badge } from "@/design-system/ui/badge";
import { Separator } from "@/design-system/ui/separator";
import {
  X,
  Code,
  Save,
  FileJson,
  Table,
  FileDown,
  RefreshCw,
  History,
  Plus,
  GripVertical,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import Editor from "@monaco-editor/react";
import Split from "react-split";

interface NodeInspectorProps {
  node?: {
    id: string;
    type: string;
    data: Record<string, unknown>;
  };
  onClose?: () => void;
  onSave?: (nodeId: string, data: Record<string, unknown>) => void;
  className?: string;
  variant?: "modal" | "panel";
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
}

interface SchemaField {
  name: string;
  type: string;
  path: string;
  description?: string;
}

export default function NodeInspector({
  node,
  onClose,
  onSave,
  className,
  variant = "modal",
  isCollapsed = false,
  onToggleCollapse,
}: NodeInspectorProps) {
  const [useLiveData, setUseLiveData] = useState(true);
  const [pythonCode, setPythonCode] = useState(
    `def process_data(input_data):\n    # Add your Python code here\n    result = input_data\n    \n    # Example: Filter items with value > 100\n    if "items" in input_data:\n        result = {\n            "filtered_items": [item for item in input_data["items"] if item["value"] > 100]\n        }\n    \n    return result`,
  );
  const [inputViewMode, setInputViewMode] = useState("input-json");
  const [outputViewMode, setOutputViewMode] = useState("output-json");
  const [draggingField, setDraggingField] = useState<SchemaField | null>(null);
  const configTextareaRef = useRef<HTMLTextAreaElement>(null);

  if (!node) return null;

  const isPanel = variant === "panel";
  const collapsed = isPanel && isCollapsed;

  const handleSave = () => {
    if (onSave && node) {
      onSave(node.id, node.data);
    }
  };

  // Sample JSON output for demonstration
  const sampleOutput = {
    result: {
      id: "123456",
      name: "Sample Response",
      status: "success",
      timestamp: new Date().toISOString(),
      data: {
        items: [
          { id: 1, name: "Item 1", value: 100 },
          { id: 2, name: "Item 2", value: 200 },
          { id: 3, name: "Item 3", value: 300 },
        ],

        total: 3,
        processed: true,
      },
    },
  };

  // Sample input data for demonstration
  const sampleInput = {
    query: {
      filter: "status:active",
      limit: 10,
    },
    headers: {
      "Content-Type": "application/json",
      Authorization: "Bearer {{auth.token}}",
    },
  };

  // Sample schema fields for demonstration
  const sampleSchemaFields: SchemaField[] = [
    { name: "query", type: "object", path: "query" },
    { name: "filter", type: "string", path: "query.filter" },
    { name: "limit", type: "number", path: "query.limit" },
    { name: "headers", type: "object", path: "headers" },
    { name: "Content-Type", type: "string", path: "headers.Content-Type" },
    { name: "Authorization", type: "string", path: "headers.Authorization" },
  ];

  const handleDragStart = (field: SchemaField) => {
    setDraggingField(field);
  };

  const handleDragEnd = () => {
    setDraggingField(null);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (draggingField && configTextareaRef.current) {
      const textarea = configTextareaRef.current;
      const cursorPosition = textarea.selectionStart;
      const textBefore = textarea.value.substring(0, cursorPosition);
      const textAfter = textarea.value.substring(cursorPosition);

      const variableReference = `{{${draggingField.path}}}`;

      textarea.value = textBefore + variableReference + textAfter;

      // Set cursor position after the inserted variable
      const newCursorPosition = cursorPosition + variableReference.length;
      textarea.selectionStart = newCursorPosition;
      textarea.selectionEnd = newCursorPosition;
      textarea.focus();
    }
  };

  const renderInputContent = () => (
    <div className="flex h-full flex-col">
      <div className="border-b border-border">
        <Tabs defaultValue={inputViewMode} onValueChange={setInputViewMode}>
          <TabsList className="w-full justify-start h-10 rounded-none bg-transparent p-0">
            <TabsTrigger
              value="input-json"
              className="rounded-none data-[state=active]:bg-muted"
            >
              <FileJson className="h-4 w-4 mr-2" />
              JSON
            </TabsTrigger>
            <TabsTrigger
              value="input-table"
              className="rounded-none data-[state=active]:bg-muted"
            >
              <Table className="h-4 w-4 mr-2" />
              Table
            </TabsTrigger>
            <TabsTrigger
              value="input-schema"
              className="rounded-none data-[state=active]:bg-muted"
            >
              <Code className="h-4 w-4 mr-2" />
              Schema
            </TabsTrigger>
          </TabsList>

          <TabsContent value="input-json" className="p-0 m-0">
            <div className="flex-1 p-4 bg-muted/30">
              <div className="font-mono text-sm whitespace-pre overflow-auto rounded-md bg-muted p-4 h-full">
                {JSON.stringify(sampleInput, null, 2)}
              </div>
            </div>
          </TabsContent>

          <TabsContent value="input-table" className="p-0 m-0">
            <div className="flex-1 p-4 bg-muted/30">
              <div className="font-mono text-sm overflow-auto rounded-md bg-muted p-4 h-full">
                <p>Table view not implemented</p>
              </div>
            </div>
          </TabsContent>

          <TabsContent value="input-schema" className="p-0 m-0">
            <div className="flex-1 p-4 bg-muted/30">
              <div className="font-mono text-sm overflow-auto rounded-md bg-muted p-4 h-full">
                <div className="space-y-2">
                  {sampleSchemaFields.map((field) => (
                    <div
                      key={field.path}
                      className="flex items-center justify-between p-2 bg-background rounded border border-border hover:border-primary/50 cursor-grab"
                      draggable
                      onDragStart={() => handleDragStart(field)}
                      onDragEnd={handleDragEnd}
                    >
                      <div className="flex items-center gap-2">
                        <GripVertical className="h-4 w-4 text-muted-foreground" />

                        <span className="font-medium">{field.name}</span>
                        <Badge variant="outline" className="text-xs">
                          {field.type}
                        </Badge>
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {field.path}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );

  const renderConfigContent = () => (
    <ScrollArea className="h-full">
      <div
        className="p-6 space-y-6"
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
      >
        <div className="space-y-4">
          <h3 className="text-lg font-medium">Basic Settings</h3>
          <div className="grid gap-4">
            <div className="grid gap-2">
              <Label htmlFor="node-name">Node Name</Label>
              <Input
                id="node-name"
                defaultValue={node.data.label || ""}
                placeholder="Enter node name"
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="node-description">Description</Label>
              <Textarea
                id="node-description"
                defaultValue={node.data.description || ""}
                placeholder="Enter description"
                rows={3}
                ref={configTextareaRef}
              />
            </div>
          </div>
        </div>

        <Separator />

        {node.type === "HTTP Request" && (
          <div className="space-y-4">
            <h3 className="text-lg font-medium">HTTP Settings</h3>
            <div className="grid gap-4">
              <div className="grid gap-2">
                <Label htmlFor="request-method">Method</Label>
                <Select defaultValue="GET">
                  <SelectTrigger>
                    <SelectValue placeholder="Select method" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="GET">GET</SelectItem>
                    <SelectItem value="POST">POST</SelectItem>
                    <SelectItem value="PUT">PUT</SelectItem>
                    <SelectItem value="DELETE">DELETE</SelectItem>
                    <SelectItem value="PATCH">PATCH</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="grid gap-2">
                <Label htmlFor="request-url">URL</Label>
                <Input
                  id="request-url"
                  defaultValue="https://api.example.com/data"
                  placeholder="Enter URL"
                />
              </div>

              <div className="grid gap-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="request-headers">Headers</Label>
                  <Button variant="ghost" size="sm" className="h-8 px-2">
                    <Plus className="h-3 w-3 mr-1" />
                    Add Header
                  </Button>
                </div>
                <div className="space-y-2">
                  <div className="grid grid-cols-2 gap-2">
                    <Input placeholder="Key" defaultValue="Content-Type" />

                    <Input
                      placeholder="Value"
                      defaultValue="application/json"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <Input placeholder="Key" defaultValue="Authorization" />

                    <Input
                      placeholder="Value"
                      defaultValue="Bearer {{auth.token}}"
                    />
                  </div>
                </div>
              </div>

              <div className="grid gap-2">
                <Label htmlFor="request-body">Request Body</Label>
                <div className="relative">
                  <Textarea
                    id="request-body"
                    defaultValue='{\n  "query": "example",\n  "limit": 10\n}'
                    className="font-mono min-h-[150px]"
                  />

                  <Button
                    variant="ghost"
                    size="icon"
                    className="absolute top-2 right-2 h-6 w-6 bg-background/80"
                  >
                    <Code className="h-3 w-3" />
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}

        {node.type === "Transform Data" && (
          <div className="space-y-4">
            <h3 className="text-lg font-medium">Transformation Settings</h3>
            <div className="grid gap-4">
              <div className="grid gap-2">
                <Label htmlFor="transform-mode">Mode</Label>
                <Select defaultValue="jmespath">
                  <SelectTrigger>
                    <SelectValue placeholder="Select mode" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="jmespath">JMESPath</SelectItem>
                    <SelectItem value="jsonata">JSONata</SelectItem>
                    <SelectItem value="custom">Custom Code</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="grid gap-2">
                <Label htmlFor="transform-expression">Expression</Label>
                <div className="relative">
                  <Textarea
                    id="transform-expression"
                    defaultValue="data.items[?value > `100`]"
                    className="font-mono min-h-[150px]"
                  />

                  <Button
                    variant="ghost"
                    size="icon"
                    className="absolute top-2 right-2 h-6 w-6 bg-background/80"
                  >
                    <Code className="h-3 w-3" />
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}

        {node.type === "Python" && (
          <div className="space-y-4">
            <h3 className="text-lg font-medium">Python Code</h3>
            <div className="grid gap-2">
              <Label htmlFor="python-code">Code</Label>
              <div className="border rounded-md overflow-hidden h-[300px]">
                {typeof window !== "undefined" && (
                  <Editor
                    height="100%"
                    defaultLanguage="python"
                    value={pythonCode}
                    onChange={(value) => setPythonCode(value || "")}
                    options={{
                      minimap: { enabled: false },
                      scrollBeyondLastLine: false,
                      fontSize: 14,
                      lineNumbers: "on",
                    }}
                    theme="vs-dark"
                  />
                )}
              </div>
            </div>
          </div>
        )}

        <Separator />

        <div className="space-y-4">
          <h3 className="text-lg font-medium">Advanced Options</h3>
          <div className="grid gap-4">
            <div className="flex items-center justify-between">
              <Label htmlFor="retry-failed">Retry on failure</Label>
              <Switch id="retry-failed" />
            </div>

            <div className="flex items-center justify-between">
              <Label htmlFor="continue-on-fail">Continue on failure</Label>
              <Switch id="continue-on-fail" />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="timeout">Timeout (seconds)</Label>
              <Input
                id="timeout"
                type="number"
                defaultValue="30"
                min="1"
                max="300"
              />
            </div>
          </div>
        </div>
      </div>
    </ScrollArea>
  );

  const renderOutputContent = () => (
    <div className="flex h-full flex-col">
      <div className="border-b border-border">
        <div className="flex items-center justify-between">
          <Tabs defaultValue={outputViewMode} onValueChange={setOutputViewMode}>
            <TabsList className="w-full justify-start h-10 rounded-none bg-transparent p-0">
              <TabsTrigger
                value="output-json"
                className="rounded-none data-[state=active]:bg-muted"
              >
                <FileJson className="h-4 w-4 mr-2" />
                JSON
              </TabsTrigger>
              <TabsTrigger
                value="output-table"
                className="rounded-none data-[state=active]:bg-muted"
              >
                <Table className="h-4 w-4 mr-2" />
                Table
              </TabsTrigger>
              <TabsTrigger
                value="output-schema"
                className="rounded-none data-[state=active]:bg-muted"
              >
                <Code className="h-4 w-4 mr-2" />
                Schema
              </TabsTrigger>
            </TabsList>

            <div className="flex items-center gap-2 pr-2">
              <div className="flex items-center space-x-2 mr-2">
                <Switch
                  id="live-data"
                  checked={useLiveData}
                  onCheckedChange={setUseLiveData}
                />

                <Label htmlFor="live-data" className="text-xs">
                  Live data
                </Label>
              </div>
              <Button variant="ghost" size="icon" className="h-8 w-8">
                <RefreshCw className="h-4 w-4" />
              </Button>
            </div>
          </Tabs>
        </div>
      </div>

      <Tabs defaultValue={outputViewMode}>
        <TabsContent value="output-json" className="p-0 m-0 h-full">
          <div className="flex-1 p-4 bg-muted/30 relative h-full">
            {useLiveData ? (
              <div className="font-mono text-sm whitespace-pre overflow-auto rounded-md bg-muted p-4 h-full">
                {JSON.stringify(sampleOutput, null, 2)}
              </div>
            ) : (
              <div className="flex items-center justify-center h-full">
                <div className="text-center">
                  <Badge variant="outline" className="mb-2">
                    Sample Data
                  </Badge>
                  <p className="text-sm text-muted-foreground">
                    Using cached sample data
                  </p>
                </div>
              </div>
            )}
          </div>
        </TabsContent>

        <TabsContent value="output-table" className="p-0 m-0 h-full">
          <div className="flex-1 p-4 bg-muted/30 relative h-full">
            <div className="font-mono text-sm overflow-auto rounded-md bg-muted p-4 h-full">
              <p>Table view not implemented</p>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="output-schema" className="p-0 m-0 h-full">
          <div className="flex-1 p-4 bg-muted/30 relative h-full">
            <div className="font-mono text-sm overflow-auto rounded-md bg-muted p-4 h-full">
              <p>Schema view not implemented</p>
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );

  const header = (
    <div className="flex items-center justify-between px-4 py-3 border-b border-border">
      <div className="flex items-center gap-2">
        {isPanel && (
          <Button
            variant="ghost"
            size="icon"
            onClick={onToggleCollapse}
            aria-label={
              collapsed ? "Expand inspector panel" : "Collapse inspector panel"
            }
            disabled={!onToggleCollapse}
          >
            <ChevronRight
              className={cn(
                "h-4 w-4 transition-transform",
                collapsed ? "" : "rotate-180",
              )}
            />
          </Button>
        )}
        {!collapsed && (
          <div className="flex flex-col min-w-0">
            <h3 className="font-medium capitalize truncate">{node.type}</h3>
            <p className="text-xs text-muted-foreground truncate">
              ID: {node.id}
            </p>
          </div>
        )}
      </div>
      {!collapsed && (
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            aria-label="Close inspector"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  );

  const splitContent = (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="flex-1 overflow-hidden">
        <Split
          sizes={[33, 67]}
          minSize={150}
          expandToMin={false}
          gutterSize={10}
          gutterAlign="center"
          snapOffset={30}
          dragInterval={1}
          direction="horizontal"
          cursor="col-resize"
          className="flex h-full"
          gutterStyle={() => ({
            backgroundColor: "hsl(var(--border))",
            width: "4px",
            margin: "0 2px",
            cursor: "col-resize",
            "&:hover": {
              backgroundColor: "hsl(var(--primary))",
            },
            "&:active": {
              backgroundColor: "hsl(var(--primary))",
            },
          })}
        >
          <div className="h-full overflow-hidden flex flex-col">
            <div className="p-2 bg-muted/20 border-b border-border flex-shrink-0">
              <h3 className="text-sm font-medium">Input</h3>
            </div>
            <div className="flex-1 overflow-auto">{renderInputContent()}</div>
          </div>

          <Split
            sizes={[50, 50]}
            minSize={150}
            expandToMin={false}
            gutterSize={10}
            gutterAlign="center"
            snapOffset={30}
            dragInterval={1}
            direction="horizontal"
            cursor="col-resize"
            className="flex h-full"
            gutterStyle={() => ({
              backgroundColor: "hsl(var(--border))",
              width: "4px",
              margin: "0 2px",
              cursor: "col-resize",
              "&:hover": {
                backgroundColor: "hsl(var(--primary))",
              },
              "&:active": {
                backgroundColor: "hsl(var(--primary))",
              },
            })}
          >
            <div className="h-full overflow-hidden flex flex-col">
              <div className="p-2 bg-muted/20 border-b border-border flex-shrink-0">
                <h3 className="text-sm font-medium">Configuration</h3>
              </div>
              <div className="flex-1 overflow-auto">
                {renderConfigContent()}
              </div>
            </div>

            <div className="h-full overflow-hidden flex flex-col">
              <div className="p-2 bg-muted/20 border-b border-border flex-shrink-0">
                <h3 className="text-sm font-medium">Output</h3>
              </div>
              <div className="flex-1 overflow-auto">
                {renderOutputContent()}
              </div>
            </div>
          </Split>
        </Split>
      </div>
    </div>
  );

  const footer = (
    <div className="flex items-center justify-between px-4 py-3 border-t border-border">
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm">
          <History className="h-4 w-4 mr-2" />
          History
        </Button>
        <Button variant="outline" size="sm">
          <FileDown className="h-4 w-4 mr-2" />
          Export
        </Button>
      </div>
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" onClick={onClose}>
          Cancel
        </Button>
        <Button size="sm" onClick={handleSave}>
          <Save className="h-4 w-4 mr-2" />
          Save
        </Button>
      </div>
    </div>
  );

  const collapsedPlaceholder = (
    <div className="flex flex-1 items-center justify-center px-1">
      <span className="text-xs font-medium tracking-[0.35em] uppercase text-muted-foreground [writing-mode:vertical-rl]">
        Inspector
      </span>
    </div>
  );

  const containerClass = cn(
    "flex flex-col border border-border bg-background shadow-lg",
    isPanel
      ? "h-full w-full rounded-none"
      : "fixed top-[5vh] left-[5vw] w-[90vw] h-[90vh] z-50 rounded-lg",
    className,
  );

  const content = (
    <div className={containerClass} tabIndex={0}>
      {header}
      {collapsed ? (
        collapsedPlaceholder
      ) : (
        <>
          {splitContent}
          {footer}
        </>
      )}
    </div>
  );

  if (!isPanel) {
    return (
      <>
        <div
          className="fixed inset-0 bg-background/80 backdrop-blur-sm z-40"
          onClick={onClose}
        />
        {content}
      </>
    );
  }

  return content;
}
