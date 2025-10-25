import { useCallback, useEffect, useRef, useState } from "react";
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
import { Switch } from "@/design-system/ui/switch";
import { ScrollArea } from "@/design-system/ui/scroll-area";
import { Badge } from "@/design-system/ui/badge";
import {
  X,
  Code,
  Save,
  FileJson,
  Table,
  FileDown,
  RefreshCw,
  History,
  GripVertical,
} from "lucide-react";
import { cn } from "@/lib/utils";
import Editor, { type OnMount } from "@monaco-editor/react";
import type { editor as MonacoEditor } from "monaco-editor";
import Split from "react-split";
import { DEFAULT_PYTHON_CODE } from "@features/workflow/lib/python-node";
import Form from "@rjsf/core";
import {
  getNodeSchema,
  getNodeUiSchema,
} from "@features/workflow/lib/node-schemas";
import { customWidgets, customTemplates, validator } from "./rjsf-theme";

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
  const [draftData, setDraftData] = useState<Record<string, unknown>>(() =>
    node?.data ? { ...(node.data as Record<string, unknown>) } : {},
  );
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
  const [, setDraggingField] = useState<SchemaField | null>(null);
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
    setDraftData(
      node?.data ? { ...(node.data as Record<string, unknown>) } : {},
    );
  }, [isPythonNode, node]);

  const nodeLabelCandidate = node?.data?.label;
  const nodeLabel =
    typeof nodeLabelCandidate === "string" && nodeLabelCandidate.length > 0
      ? nodeLabelCandidate
      : (node?.type ?? "");
  const formattedSemanticType = semanticType
    ? `${semanticType.charAt(0).toUpperCase()}${semanticType.slice(1)}`
    : null;
  const backendType =
    node && typeof node.data?.backendType === "string"
      ? (node.data.backendType as string)
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
      const updatedData = { ...draftData };
      if (isPythonNode) {
        updatedData.code =
          pythonCode && pythonCode.length > 0
            ? pythonCode
            : DEFAULT_PYTHON_CODE;
      }
      onSave(node.id, updatedData);
    }
  }, [draftData, isPythonNode, node, onSave, pythonCode]);

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
    // Get the JSON Schema for this node type
    const schema = getNodeSchema(backendType);
    const uiSchema = getNodeUiSchema(backendType);

    // Handle form data change
    const handleFormChange = (data: { formData?: Record<string, unknown> }) => {
      if (data.formData) {
        setDraftData(data.formData);
      }
    };

    // For Python nodes, use Monaco editor instead of RJSF
    if (isPythonNode) {
      return (
        <ScrollArea className="h-full">
          <div className="p-6 space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="node-name">Node Name</Label>
              <Input
                id="node-name"
                value={
                  typeof draftData.label === "string"
                    ? draftData.label
                    : (node.data.label as string) || ""
                }
                placeholder="Enter node name"
                onChange={(event) =>
                  setDraftData((current) => ({
                    ...current,
                    label: event.target.value,
                  }))
                }
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="node-description">Description</Label>
              <Textarea
                id="node-description"
                value={
                  typeof draftData.description === "string"
                    ? draftData.description
                    : (node.data.description as string) || ""
                }
                placeholder="Enter description"
                rows={3}
                onChange={(event) =>
                  setDraftData((current) => ({
                    ...current,
                    description: event.target.value,
                  }))
                }
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="python-code">Python Code</Label>
              <div className="border rounded-md overflow-hidden h-[400px]">
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
          </div>
        </ScrollArea>
      );
    }

    // For all other nodes, use RJSF
    return (
      <ScrollArea className="h-full">
        <div className="p-6">
          <Form
            schema={schema}
            uiSchema={uiSchema}
            formData={draftData}
            onChange={handleFormChange}
            validator={validator}
            widgets={customWidgets}
            templates={customTemplates}
            onSubmit={(data) => {
              // Handle submit if needed
              console.log("Form submitted:", data);
            }}
          >
            {/* Hide the default submit button */}
            <div className="hidden" />
          </Form>
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
