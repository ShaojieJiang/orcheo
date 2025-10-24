import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import Split from "react-split";
import Editor, { type OnMount } from "@monaco-editor/react";
import type { editor as MonacoEditor } from "monaco-editor";
import { X, Save, RefreshCw, FileJson } from "lucide-react";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/design-system/ui/tabs";
import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";
import { Label } from "@/design-system/ui/label";
import { Switch } from "@/design-system/ui/switch";
import { ScrollArea } from "@/design-system/ui/scroll-area";
import { Badge } from "@/design-system/ui/badge";
import { cn } from "@/lib/utils";
import { DEFAULT_PYTHON_CODE } from "@features/workflow/lib/python-node";
import SchemaDrivenForm from "../schema-driven-form";
import type { RJSFSchema, UiSchema } from "@rjsf/utils";

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

interface NodeRuntimeData {
  inputs?: unknown;
  outputs?: unknown;
  messages?: unknown;
  raw?: unknown;
  updatedAt?: string;
}

const isRecord = (value: unknown): value is Record<string, unknown> => {
  return typeof value === "object" && value !== null;
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

const extractPythonCode = (targetNode: NodeInspectorProps["node"]): string => {
  if (!targetNode) {
    return DEFAULT_PYTHON_CODE;
  }
  const candidate = targetNode.data?.code;
  return typeof candidate === "string" && candidate.length > 0
    ? candidate
    : DEFAULT_PYTHON_CODE;
};

const pickFirstRecord = (
  candidates: Array<unknown>,
): Record<string, unknown> | undefined => {
  for (const candidate of candidates) {
    if (isRecord(candidate)) {
      return candidate;
    }
  }
  return undefined;
};

const getConfigSchema = (
  targetNode: NodeInspectorProps["node"],
): RJSFSchema | undefined => {
  if (!targetNode) {
    return undefined;
  }
  const data = targetNode.data;
  const configCandidate = isRecord(data.config)
    ? (data.config as Record<string, unknown>)
    : null;
  return pickFirstRecord([
    data.configSchema,
    data.config_schema,
    data.schema,
    configCandidate?.schema,
  ]) as RJSFSchema | undefined;
};

const getConfigUiSchema = (
  targetNode: NodeInspectorProps["node"],
): UiSchema | undefined => {
  if (!targetNode) {
    return undefined;
  }
  const data = targetNode.data;
  const configCandidate = isRecord(data.config)
    ? (data.config as Record<string, unknown>)
    : null;
  return pickFirstRecord([
    data.configUiSchema,
    data.config_ui_schema,
    data.uiSchema,
    configCandidate?.uiSchema,
  ]) as UiSchema | undefined;
};

const extractConfigFormData = (
  draft: Record<string, unknown>,
  schema: RJSFSchema | undefined,
): Record<string, unknown> | undefined => {
  if (!schema) {
    return undefined;
  }
  if (isRecord(draft.config)) {
    return { ...(draft.config as Record<string, unknown>) };
  }
  if (schema.properties && isRecord(schema.properties)) {
    const result: Record<string, unknown> = {};
    for (const key of Object.keys(
      schema.properties as Record<string, unknown>,
    )) {
      if (key in draft) {
        result[key] = draft[key];
      }
    }
    return result;
  }
  return undefined;
};

const mergeConfigIntoDraft = (
  draft: Record<string, unknown>,
  nextConfig: Record<string, unknown> | undefined,
  schema: RJSFSchema | undefined,
): Record<string, unknown> => {
  const nextDraft: Record<string, unknown> = { ...draft };
  if (!nextConfig) {
    if (isRecord(nextDraft.config)) {
      nextDraft.config = {};
    }
    if (schema?.properties && isRecord(schema.properties)) {
      for (const key of Object.keys(
        schema.properties as Record<string, unknown>,
      )) {
        delete nextDraft[key];
      }
    }
    return nextDraft;
  }

  if (isRecord(nextDraft.config)) {
    const configDraft = { ...(nextDraft.config as Record<string, unknown>) };
    for (const key of Object.keys(configDraft)) {
      if (!(key in nextConfig) || nextConfig[key] === undefined) {
        delete configDraft[key];
      }
    }
    for (const [key, value] of Object.entries(nextConfig)) {
      if (value === undefined) {
        delete configDraft[key];
      } else {
        configDraft[key] = value;
      }
    }
    nextDraft.config = configDraft;
    return nextDraft;
  }

  if (schema?.properties && isRecord(schema.properties)) {
    for (const key of Object.keys(
      schema.properties as Record<string, unknown>,
    )) {
      const value = nextConfig[key];
      if (value === undefined) {
        delete nextDraft[key];
      } else {
        nextDraft[key] = value;
      }
    }
    return nextDraft;
  }

  return { ...nextDraft, ...nextConfig };
};

const formatJson = (value: unknown): string => {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
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
  const [pythonCode, setPythonCode] = useState(() => extractPythonCode(node));
  const [activeRuntimeTab, setActiveRuntimeTab] = useState("inputs");

  const previouslyHadRuntimeRef = useRef(hasRuntime);
  const editorKeydownDisposableRef = useRef<MonacoEditor.IDisposable | null>(
    null,
  );
  const handleSaveRef = useRef<() => void>();

  const semanticType = getSemanticType(node);
  const isPythonNode = semanticType === "python";

  const configSchema = useMemo(() => getConfigSchema(node), [node]);
  const configUiSchema = useMemo(() => getConfigUiSchema(node), [node]);
  const configFormData = useMemo(
    () => extractConfigFormData(draftData, configSchema),
    [draftData, configSchema],
  );
  const initialConfigFormData = useMemo(
    () =>
      node
        ? extractConfigFormData(
            node.data as Record<string, unknown>,
            configSchema,
          )
        : undefined,
    [configSchema, node],
  );

  const formattedUpdatedAt: string | null = useMemo(() => {
    if (!runtime?.updatedAt) {
      return null;
    }
    const parsed = new Date(runtime.updatedAt);
    if (Number.isNaN(parsed.getTime())) {
      return runtime.updatedAt;
    }
    return parsed.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  }, [runtime?.updatedAt]);

  useEffect(() => {
    if (!hasRuntime) {
      setUseLiveData(false);
    } else if (!previouslyHadRuntimeRef.current) {
      setUseLiveData(true);
    }
    previouslyHadRuntimeRef.current = hasRuntime;
  }, [hasRuntime]);

  useEffect(() => {
    if (node) {
      setDraftData(
        node.data ? { ...(node.data as Record<string, unknown>) } : {},
      );
      setPythonCode(extractPythonCode(node));
      setUseLiveData(Boolean(runtime));
    }
  }, [node, runtime]);

  const handleConfigChange = useCallback(
    (next: Record<string, unknown>) => {
      setDraftData((current) =>
        mergeConfigIntoDraft(current, next, configSchema),
      );
    },
    [configSchema],
  );

  const handleEditorMount = useCallback<OnMount>((editorInstance) => {
    editorKeydownDisposableRef.current?.dispose();
    editorKeydownDisposableRef.current = editorInstance.onKeyDown((event) => {
      const { key, ctrlKey, metaKey } = event.browserEvent;
      if ((ctrlKey || metaKey) && (key === "s" || key === "S")) {
        event.browserEvent.preventDefault();
        event.browserEvent.stopPropagation();
        handleSaveRef.current?.();
      }
    });
  }, []);

  useEffect(() => {
    return () => {
      editorKeydownDisposableRef.current?.dispose();
    };
  }, []);

  const handleSave = useCallback(() => {
    if (!node || !onSave) {
      return;
    }
    const payload: Record<string, unknown> = { ...draftData };
    if (isPythonNode) {
      payload.code =
        pythonCode && pythonCode.length > 0 ? pythonCode : DEFAULT_PYTHON_CODE;
    }
    onSave(node.id, payload);
  }, [draftData, isPythonNode, node, onSave, pythonCode]);

  useEffect(() => {
    handleSaveRef.current = handleSave;
  }, [handleSave]);

  if (!node) {
    return null;
  }

  const nodeLabelCandidate = node.data?.label;
  const originalNodeLabel =
    typeof nodeLabelCandidate === "string" && nodeLabelCandidate.length > 0
      ? nodeLabelCandidate
      : node.type;
  const draftLabelValue =
    typeof draftData.label === "string" ? (draftData.label as string) : "";
  const currentLabel =
    draftLabelValue && draftLabelValue.length > 0
      ? draftLabelValue
      : originalNodeLabel;
  const formattedSemanticType = semanticType
    ? `${semanticType.charAt(0).toUpperCase()}${semanticType.slice(1)}`
    : null;

  const liveInputs = runtime?.inputs;
  const liveOutputs = runtime?.outputs;
  const liveMessages = runtime?.messages;
  const liveRaw = runtime?.raw ?? runtime;

  const renderRuntimePanel = (label: string, value: unknown) => {
    if (!hasRuntime) {
      return (
        <div className="flex flex-col items-center justify-center py-8 text-center text-sm text-muted-foreground">
          <Badge variant="outline" className="mb-2">
            {label}
          </Badge>
          <p>Run the workflow to capture live data.</p>
        </div>
      );
    }

    if (!useLiveData) {
      return (
        <div className="flex flex-col items-center justify-center py-8 text-center text-sm text-muted-foreground">
          <Badge variant="outline" className="mb-2">
            {label}
          </Badge>
          <p>Live data disabled for this view.</p>
        </div>
      );
    }

    if (value === undefined) {
      return (
        <div className="flex flex-col items-center justify-center py-8 text-center text-sm text-muted-foreground">
          <Badge variant="outline" className="mb-2">
            {label}
          </Badge>
          <p>No data captured yet.</p>
        </div>
      );
    }

    return (
      <pre className="font-mono text-sm whitespace-pre overflow-auto rounded-md bg-muted p-4">
        {formatJson(value)}
      </pre>
    );
  };

  return (
    <>
      <div
        className="fixed inset-0 bg-background/80 backdrop-blur-sm z-40"
        onClick={onClose}
      />
      <div
        className={cn(
          "fixed top-[5vh] left-[5vw] h-[90vh] w-[90vw] z-50",
          "flex flex-col overflow-hidden rounded-lg border border-border bg-background shadow-lg",
          className,
        )}
      >
        <div className="flex items-center justify-between border-b border-border p-4">
          <div className="space-y-1">
            <h3 className="text-base font-medium">{currentLabel}</h3>
            <p className="text-xs text-muted-foreground">ID: {node.id}</p>
            {formattedSemanticType ? (
              <p className="text-xs text-muted-foreground">
                Node type: {formattedSemanticType}
              </p>
            ) : null}
          </div>
          <div className="flex items-center gap-2">
            {formattedUpdatedAt ? (
              <Badge variant="outline" className="text-xs font-normal">
                Live data updated {formattedUpdatedAt}
              </Badge>
            ) : null}
            <Button variant="ghost" size="icon" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="flex-1 overflow-hidden">
          <Split
            sizes={[45, 55]}
            minSize={280}
            gutterSize={8}
            direction="horizontal"
            className="flex h-full"
            gutterStyle={() => ({
              backgroundColor: "hsl(var(--border))",
              width: "4px",
              margin: "0 2px",
            })}
          >
            <div className="flex h-full flex-col overflow-hidden">
              <div className="border-b border-border p-4">
                <h4 className="text-sm font-semibold">Configuration</h4>
              </div>
              <ScrollArea className="flex-1">
                <div className="space-y-6 p-4">
                  <div className="space-y-2">
                    <Label htmlFor="node-label">Node label</Label>
                    <Input
                      id="node-label"
                      value={draftLabelValue}
                      onChange={(event) =>
                        setDraftData((current) => ({
                          ...current,
                          label: event.target.value,
                        }))
                      }
                      placeholder={originalNodeLabel}
                    />
                  </div>

                  {configSchema ? (
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <div>
                          <h5 className="text-sm font-semibold">
                            Schema-driven configuration
                          </h5>
                          <p className="text-xs text-muted-foreground">
                            Generated from the backend JSON schema for this
                            node.
                          </p>
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          disabled={!initialConfigFormData}
                          onClick={() =>
                            setDraftData((current) =>
                              mergeConfigIntoDraft(
                                current,
                                initialConfigFormData ?? {},
                                configSchema,
                              ),
                            )
                          }
                        >
                          <RefreshCw className="h-4 w-4" />
                        </Button>
                      </div>
                      <SchemaDrivenForm
                        schema={configSchema}
                        uiSchema={configUiSchema}
                        formData={configFormData}
                        onChange={handleConfigChange}
                        onSubmit={() => handleSaveRef.current?.()}
                      />
                    </div>
                  ) : (
                    <div className="rounded-md border border-dashed border-border p-4 text-sm text-muted-foreground">
                      <p>No JSON schema provided for this node.</p>
                      <p className="text-xs">
                        Define a Pydantic config on the node to enable automatic
                        forms.
                      </p>
                    </div>
                  )}

                  {isPythonNode ? (
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <Label>Python code</Label>
                        <Badge
                          variant="outline"
                          className="text-xs font-normal"
                        >
                          Press Ctrl+S / Cmd+S to save
                        </Badge>
                      </div>
                      <div className="rounded-md border border-border">
                        <Editor
                          height="240px"
                          defaultLanguage="python"
                          theme="vs-dark"
                          value={pythonCode}
                          onChange={(value) =>
                            setPythonCode(value ?? DEFAULT_PYTHON_CODE)
                          }
                          onMount={handleEditorMount}
                          options={{
                            minimap: { enabled: false },
                            fontSize: 14,
                          }}
                        />
                      </div>
                    </div>
                  ) : null}
                </div>
              </ScrollArea>
            </div>

            <div className="flex h-full flex-col overflow-hidden">
              <div className="flex items-center justify-between border-b border-border p-4">
                <div>
                  <h4 className="text-sm font-semibold">Runtime data</h4>
                  <p className="text-xs text-muted-foreground">
                    Inspect the inputs and outputs captured from workflow runs.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Switch
                    id="use-live-data"
                    checked={useLiveData && hasRuntime}
                    disabled={!hasRuntime}
                    onCheckedChange={(checked) =>
                      setUseLiveData(Boolean(checked))
                    }
                  />
                  <Label
                    htmlFor="use-live-data"
                    className="text-xs text-muted-foreground"
                  >
                    Use live data
                  </Label>
                </div>
              </div>
              <Tabs
                value={activeRuntimeTab}
                onValueChange={setActiveRuntimeTab}
                className="flex h-full flex-col"
              >
                <TabsList className="flex h-10 items-center gap-2 border-b border-border bg-muted/40 px-4">
                  <TabsTrigger value="inputs" className="gap-2 text-xs">
                    <FileJson className="h-3 w-3" /> Inputs
                  </TabsTrigger>
                  <TabsTrigger value="outputs" className="gap-2 text-xs">
                    <FileJson className="h-3 w-3" /> Outputs
                  </TabsTrigger>
                  <TabsTrigger value="messages" className="gap-2 text-xs">
                    <FileJson className="h-3 w-3" /> Messages
                  </TabsTrigger>
                  <TabsTrigger value="raw" className="gap-2 text-xs">
                    <FileJson className="h-3 w-3" /> Raw payload
                  </TabsTrigger>
                </TabsList>
                <TabsContent
                  value="inputs"
                  className="flex-1 overflow-hidden p-4"
                >
                  {renderRuntimePanel("Inputs", liveInputs)}
                </TabsContent>
                <TabsContent
                  value="outputs"
                  className="flex-1 overflow-hidden p-4"
                >
                  {renderRuntimePanel("Outputs", liveOutputs)}
                </TabsContent>
                <TabsContent
                  value="messages"
                  className="flex-1 overflow-hidden p-4"
                >
                  {renderRuntimePanel("Messages", liveMessages)}
                </TabsContent>
                <TabsContent value="raw" className="flex-1 overflow-hidden p-4">
                  {renderRuntimePanel("Raw", liveRaw)}
                </TabsContent>
              </Tabs>
            </div>
          </Split>
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-border p-4">
          <Button variant="outline" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button size="sm" onClick={handleSave}>
            <Save className="mr-2 h-4 w-4" /> Save
          </Button>
        </div>
      </div>
    </>
  );
}
