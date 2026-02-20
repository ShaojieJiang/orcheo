import { useMemo } from "react";
import { ScrollArea } from "@/design-system/ui/scroll-area";
import { Label } from "@/design-system/ui/label";
import { Input } from "@/design-system/ui/input";
import { Textarea } from "@/design-system/ui/textarea";
import Editor, { type OnMount } from "@monaco-editor/react";
import {
  getNodeSchema,
  getNodeUiSchema,
} from "@features/workflow/lib/node-schemas";
import { SchemaConfigForm } from "@features/workflow/components/forms/schema-config-form";
import type { NodeInspectorProps } from "./types";
import type { Dispatch, SetStateAction } from "react";

interface ConfigPanelProps {
  backendType: string | null;
  isPythonNode: boolean;
  draftData: Record<string, unknown>;
  setDraftData: Dispatch<SetStateAction<Record<string, unknown>>>;
  node: NonNullable<NodeInspectorProps["node"]>;
  pythonCode: string;
  onPythonCodeChange: (code: string) => void;
  onEditorMount: OnMount;
}

export function ConfigPanel({
  backendType,
  isPythonNode,
  draftData,
  setDraftData,
  node,
  pythonCode,
  onPythonCodeChange,
  onEditorMount,
}: ConfigPanelProps) {
  const schema = useMemo(() => getNodeSchema(backendType), [backendType]);
  const uiSchema = useMemo(() => getNodeUiSchema(backendType), [backendType]);

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
                  onChange={(value) => onPythonCodeChange(value || "")}
                  onMount={onEditorMount}
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

  return (
    <ScrollArea className="h-full">
      <div className="p-6">
        <SchemaConfigForm
          schema={schema}
          uiSchema={uiSchema}
          formData={draftData}
          onChange={(nextFormData) => {
            setDraftData(nextFormData);
          }}
        />
      </div>
    </ScrollArea>
  );
}
