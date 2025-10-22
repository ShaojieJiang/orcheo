import React, { useCallback, useEffect, useRef, useState } from "react";
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
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/design-system/ui/accordion";
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
} from "lucide-react";
import { cn } from "@/lib/utils";
import Editor, { type OnMount } from "@monaco-editor/react";
import type { editor as MonacoEditor } from "monaco-editor";
import Split from "react-split";
import { DEFAULT_PYTHON_CODE } from "@features/workflow/lib/python-node";

interface NodeInspectorProps {
  node?: {
    id: string;
    type: string;
    data: Record<string, unknown>;
  };
  onClose?: () => void;
  onSave?: (nodeId: string, data: Record<string, unknown>) => void;
  className?: string;
}

interface SchemaField {
  name: string;
  type: string;
  path: string;
  description?: string;
}

type NodeRuntimeData = {
  inputs?: unknown;
  outputs?: unknown;
  messages?: unknown;
  raw?: unknown;
  updatedAt?: string;
};

const isRecord = (value: unknown): value is Record<string, unknown> => {
  return typeof value === "object" && value !== null;
};

export default function NodeInspector({
  node,
  onClose,
  onSave,
  className,
}: NodeInspectorProps) {
  const runtimeCandidate = node
    ? (node.data as Record<string, unknown>)["runtime"]
    : undefined;
  const runtime = isRecord(runtimeCandidate)
    ? (runtimeCandidate as NodeRuntimeData)
    : null;
  const hasRuntime = Boolean(runtime);
  const [useLiveData, setUseLiveData] = useState(hasRuntime);
  const extractPythonCode = (
    targetNode: NodeInspectorProps["node"],
  ): string => {
    if (!targetNode) {
      return DEFAULT_PYTHON_CODE;
    }
    const candidate = targetNode.data?.code;
    return typeof candidate === "string" && candidate.length > 0
      ? candidate
      : DEFAULT_PYTHON_CODE;
  };

  const getSemanticType = (
    targetNode: NodeInspectorProps["node"],
  ): string | null => {
    if (!targetNode) {
      return null;
    }
    const dataType = targetNode.data?.type;
    if (typeof dataType === "string" && dataType.length > 0) {
      return dataType.toLowerCase();
    }
    return typeof targetNode.type === "string" && targetNode.type.length > 0
      ? targetNode.type.toLowerCase()
      : null;
  };

  const [pythonCode, setPythonCode] = useState(() => extractPythonCode(node));
  const [inputViewMode, setInputViewMode] = useState("input-json");
  const [outputViewMode, setOutputViewMode] = useState("output-json");
  const [draggingField, setDraggingField] = useState<SchemaField | null>(null);
  const configTextareaRef = useRef<HTMLTextAreaElement>(null);
  const previouslyHadRuntimeRef = useRef(hasRuntime);
  const editorKeydownDisposableRef = useRef<MonacoEditor.IDisposable | null>(
    null,
  );
  const handleSaveRef = useRef<() => void>();

  const semanticType = getSemanticType(node);
  const isPythonNode = semanticType === "python";

  useEffect(() => {
    if (!hasRuntime) {
      setUseLiveData(false);
    } else if (!previouslyHadRuntimeRef.current) {
      setUseLiveData(true);
    }
    previouslyHadRuntimeRef.current = hasRuntime;
  }, [hasRuntime]);

  useEffect(() => {
    if (node && isPythonNode) {
      setPythonCode(extractPythonCode(node));
    }
  }, [isPythonNode, node]);

  const nodeLabelCandidate = node?.data?.label;
  const nodeLabel =
    typeof nodeLabelCandidate === "string" && nodeLabelCandidate.length > 0
      ? nodeLabelCandidate
      : (node?.type ?? "");
  const formattedSemanticType = semanticType
    ? `${semanticType.charAt(0).toUpperCase()}${semanticType.slice(1)}`
    : null;

  const renderLiveDataUnavailable = (label: string) => (
    <div className="flex items-center justify-center h-full">
      <div className="text-center">
        <Badge variant="outline" className="mb-2">
          {label}
        </Badge>
        <p className="text-sm text-muted-foreground">
          {runtime
            ? "No live data captured for this node yet."
            : "Run the workflow to capture live data."}
        </p>
      </div>
    </div>
  );

  const liveInputs = runtime?.inputs;
  let outputDisplay: unknown = runtime?.raw;
  if (runtime?.outputs !== undefined || runtime?.messages !== undefined) {
    const merged: Record<string, unknown> = {};
    if (runtime.outputs !== undefined) {
      merged.outputs = runtime.outputs;
    }
    if (runtime.messages !== undefined) {
      merged.messages = runtime.messages;
    }
    outputDisplay =
      runtime.outputs !== undefined && runtime.messages === undefined
        ? runtime.outputs
        : merged;
  }
  const hasLiveInputs = liveInputs !== undefined;
  const hasLiveOutputs =
    runtime?.outputs !== undefined ||
    runtime?.messages !== undefined ||
    outputDisplay !== undefined;

  let formattedUpdatedAt: string | null = null;
  if (runtime?.updatedAt) {
    const parsed = new Date(runtime.updatedAt);
    formattedUpdatedAt = Number.isNaN(parsed.getTime())
      ? runtime.updatedAt
      : parsed.toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        });
  }

  const handleSave = useCallback(() => {
    if (onSave && node) {
      const updatedData = { ...(node.data as Record<string, unknown>) };
      if (isPythonNode) {
        updatedData.code =
          pythonCode && pythonCode.length > 0
            ? pythonCode
            : DEFAULT_PYTHON_CODE;
      }
      onSave(node.id, updatedData);
    }
  }, [isPythonNode, node, onSave, pythonCode]);

  useEffect(() => {
    handleSaveRef.current = handleSave;
  }, [handleSave]);

  useEffect(() => {
    return () => {
      editorKeydownDisposableRef.current?.dispose();
    };
  }, []);

  const handleEditorMount = useCallback<OnMount>((editorInstance) => {
    editorKeydownDisposableRef.current?.dispose();
    editorKeydownDisposableRef.current = editorInstance.onKeyDown((event) => {
      const { key, ctrlKey, metaKey, altKey } = event.browserEvent;

      const isPlainSpace =
        (key === " " || key === "Spacebar") && !ctrlKey && !metaKey && !altKey;

      if (isPlainSpace) {
        event.browserEvent.stopPropagation();
        return;
      }

      if ((ctrlKey || metaKey) && (key === "s" || key === "S")) {
        event.browserEvent.preventDefault();
        event.browserEvent.stopPropagation();
        handleSaveRef.current?.();
      }
    });
  }, []);

  if (!node) return null;

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
              {useLiveData ? (
                hasLiveInputs ? (
                  <pre className="font-mono text-sm whitespace-pre overflow-auto rounded-md bg-muted p-4 h-full">
                    {JSON.stringify(liveInputs, null, 2)}
                  </pre>
                ) : (
                  renderLiveDataUnavailable("Live Input")
                )
              ) : (
                <pre className="font-mono text-sm whitespace-pre overflow-auto rounded-md bg-muted p-4 h-full">
                  {JSON.stringify(sampleInput, null, 2)}
                </pre>
              )}
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

  const renderConfigContent = () => {
    const configurationSections: {
      id: string;
      title: string;
      content: React.ReactNode;
      defaultOpen?: boolean;
    }[] = [
      {
        id: "basic",
        title: "Basic Settings",
        defaultOpen: true,
        content: (
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
        ),
      },
    ];

    if (node.type === "HTTP Request") {
      configurationSections.push({
        id: "http",
        title: "HTTP Settings",
        content: (
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

                  <Input placeholder="Value" defaultValue="application/json" />
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
                  defaultValue='{
  "query": "example",
  "limit": 10
}'
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
        ),
      });
    }

    if (node.type === "Transform Data") {
      configurationSections.push({
        id: "transform",
        title: "Transformation Settings",
        content: (
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
        ),
      });
    }

    if (isPythonNode) {
      configurationSections.push({
        id: "python",
        title: "Python Code",
        content: (
          <div className="grid gap-2">
            <Label htmlFor="python-code">Code</Label>
            <div className="border rounded-md overflow-hidden h-[300px]">
              {typeof window !== "undefined" && (
                <Editor
                  height="100%"
                  defaultLanguage="python"
                  value={pythonCode}
                  onChange={(value) => setPythonCode(value || "")}
                  onMount={handleEditorMount}
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
        ),
      });
    }

    configurationSections.push({
      id: "advanced",
      title: "Advanced Options",
      content: (
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
      ),
    });

    const defaultItems = configurationSections
      .filter((section) => section.defaultOpen ?? true)
      .map((section) => section.id);

    return (
      <ScrollArea className="h-full">
        <div
          className="p-6"
          onDragOver={(e) => e.preventDefault()}
          onDrop={handleDrop}
        >
          <Accordion
            type="multiple"
            defaultValue={defaultItems}
            className="space-y-3"
          >
            {configurationSections.map((section) => (
              <AccordionItem
                key={section.id}
                value={section.id}
                className="border border-border/50 rounded-lg bg-background/60 backdrop-blur supports-[backdrop-filter]:bg-background/40"
              >
                <AccordionTrigger className="px-4 py-2 text-left text-sm font-medium hover:no-underline">
                  {section.title}
                </AccordionTrigger>
                <AccordionContent className="px-4 pb-4 pt-0">
                  <div className="pt-2 space-y-4 text-sm text-foreground">
                    {section.content}
                  </div>
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </div>
      </ScrollArea>
    );
  };
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
                  disabled={!runtime}
                />

                <Label htmlFor="live-data" className="text-xs">
                  Live data
                </Label>
              </div>
              <Button variant="ghost" size="icon" className="h-8 w-8">
                <RefreshCw className="h-4 w-4" />
              </Button>
              {formattedUpdatedAt && runtime && (
                <span className="text-[10px] text-muted-foreground">
                  Updated {formattedUpdatedAt}
                </span>
              )}
            </div>
          </Tabs>
        </div>
      </div>

      <Tabs defaultValue={outputViewMode}>
        <TabsContent value="output-json" className="p-0 m-0 h-full">
          <div className="flex-1 p-4 bg-muted/30 relative h-full">
            {useLiveData ? (
              hasLiveOutputs && outputDisplay !== undefined ? (
                <pre className="font-mono text-sm whitespace-pre overflow-auto rounded-md bg-muted p-4 h-full">
                  {JSON.stringify(outputDisplay, null, 2)}
                </pre>
              ) : (
                renderLiveDataUnavailable("Live Output")
              )
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

  return (
    <>
      <div
        className="fixed inset-0 bg-background/80 backdrop-blur-sm z-50"
        onClick={onClose}
      />
      <div
        className={cn(
          "flex flex-col border border-border rounded-lg bg-background shadow-lg",
          "fixed top-[5vh] left-[5vw] w-[90vw] h-[90vh] z-50",
          className,
        )}
        tabIndex={0}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="flex flex-col">
              <h3 className="font-medium">{nodeLabel}</h3>
              <p className="text-xs text-muted-foreground">ID: {node.id}</p>
              {formattedSemanticType && (
                <p className="text-xs text-muted-foreground">
                  Node type: {formattedSemanticType}
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

        {/* Split Pane Content */}
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
                <div className="flex-1 overflow-auto">
                  {renderInputContent()}
                </div>
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

        {/* Footer */}
        <div className="flex items-center justify-between p-4 border-t border-border">
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
      </div>
    </>
  );
}
