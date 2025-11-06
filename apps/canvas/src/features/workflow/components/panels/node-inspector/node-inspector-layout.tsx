import type { Dispatch, SetStateAction } from "react";
import Split from "react-split";
import { Button } from "@/design-system/ui/button";
import { X, FileDown, Play, Save, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { InputPanel } from "./input-panel";
import { ConfigPanel } from "./config-panel";
import { OutputPanel } from "./output-panel";
import type { OnMount } from "@monaco-editor/react";
import type {
  NodeInspectorProps,
  NodeRuntimeCacheEntry,
  SchemaField,
} from "./types";

const splitGutterStyle = () => ({
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
});

const splitBaseProps = {
  minSize: 150,
  gutterSize: 10,
  gutterAlign: "center" as const,
  snapOffset: 30,
  dragInterval: 1,
  direction: "horizontal" as const,
  cursor: "col-resize" as const,
  className: "flex h-full",
  gutterStyle: splitGutterStyle,
};

interface NodeInspectorLayoutProps {
  node: NonNullable<NodeInspectorProps["node"]>;
  className?: string;
  nodeLabel: string;
  formattedSemanticType: string | null;
  onClose?: () => void;
  inputViewMode: string;
  onInputViewModeChange: (value: string) => void;
  useLiveData: boolean;
  hasRuntime: boolean;
  hasLiveInputs: boolean;
  liveInputs: unknown;
  hasUpstreamConnections: boolean;
  upstreamOutputs: Record<string, unknown>;
  schemaFields: SchemaField[];
  backendType: string | null;
  isPythonNode: boolean;
  draftData: Record<string, unknown>;
  setDraftData: Dispatch<SetStateAction<Record<string, unknown>>>;
  pythonCode: string;
  onPythonCodeChange: (code: string) => void;
  onEditorMount: OnMount;
  outputViewMode: string;
  onOutputViewModeChange: (value: string) => void;
  onToggleLiveData: (value: boolean) => void;
  runtime: NodeRuntimeCacheEntry | null;
  formattedUpdatedAt: string | null;
  testResult: unknown;
  testError: string | null;
  hasLiveOutputs: boolean;
  outputDisplay: unknown;
  onTestNode: () => Promise<void>;
  isTestingNode: boolean;
  onSave: () => void;
}

export function NodeInspectorLayout({
  node,
  className,
  nodeLabel,
  formattedSemanticType,
  onClose,
  inputViewMode,
  onInputViewModeChange,
  useLiveData,
  hasRuntime,
  hasLiveInputs,
  liveInputs,
  hasUpstreamConnections,
  upstreamOutputs,
  schemaFields,
  backendType,
  isPythonNode,
  draftData,
  setDraftData,
  pythonCode,
  onPythonCodeChange,
  onEditorMount,
  outputViewMode,
  onOutputViewModeChange,
  onToggleLiveData,
  runtime,
  formattedUpdatedAt,
  testResult,
  testError,
  hasLiveOutputs,
  outputDisplay,
  onTestNode,
  isTestingNode,
  onSave,
}: NodeInspectorLayoutProps) {
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

        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="flex-1 overflow-hidden">
            <Split {...splitBaseProps} sizes={[33, 67]}>
              <div className="h-full overflow-hidden flex flex-col">
                <div className="p-2 bg-muted/20 border-b border-border flex-shrink-0">
                  <h3 className="text-sm font-medium">Input</h3>
                </div>
                <div className="flex-1 overflow-auto">
                  <InputPanel
                    inputViewMode={inputViewMode}
                    onInputViewModeChange={onInputViewModeChange}
                    useLiveData={useLiveData}
                    hasRuntime={hasRuntime}
                    hasLiveInputs={hasLiveInputs}
                    liveInputs={liveInputs}
                    hasUpstreamConnections={hasUpstreamConnections}
                    upstreamInputs={
                      hasUpstreamConnections ? upstreamOutputs : {}
                    }
                    schemaFields={schemaFields}
                  />
                </div>
              </div>

              <Split {...splitBaseProps} sizes={[50, 50]}>
                <div className="h-full overflow-hidden flex flex-col">
                  <div className="p-2 bg-muted/20 border-b border-border flex-shrink-0">
                    <h3 className="text-sm font-medium">Configuration</h3>
                  </div>
                  <div className="flex-1 overflow-auto">
                    <ConfigPanel
                      backendType={backendType}
                      isPythonNode={isPythonNode}
                      draftData={draftData}
                      setDraftData={setDraftData}
                      node={node}
                      pythonCode={pythonCode}
                      onPythonCodeChange={onPythonCodeChange}
                      onEditorMount={onEditorMount}
                    />
                  </div>
                </div>

                <div className="h-full overflow-hidden flex flex-col">
                  <div className="p-2 bg-muted/20 border-b border-border flex-shrink-0">
                    <h3 className="text-sm font-medium">Output</h3>
                  </div>
                  <div className="flex-1 overflow-auto">
                    <OutputPanel
                      outputViewMode={outputViewMode}
                      onOutputViewModeChange={onOutputViewModeChange}
                      useLiveData={useLiveData}
                      onToggleLiveData={onToggleLiveData}
                      runtime={runtime}
                      formattedUpdatedAt={formattedUpdatedAt}
                      testResult={testResult}
                      testError={testError}
                      hasRuntime={hasRuntime}
                      hasLiveOutputs={hasLiveOutputs}
                      outputDisplay={outputDisplay}
                    />
                  </div>
                </div>
              </Split>
            </Split>
          </div>
        </div>

        <div className="flex items-center justify-between p-4 border-t border-border">
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={onTestNode}
              disabled={isTestingNode}
            >
              {isTestingNode ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Testing...
                </>
              ) : (
                <>
                  <Play className="h-4 w-4 mr-2" />
                  Test Node
                </>
              )}
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
            <Button size="sm" onClick={onSave}>
              <Save className="h-4 w-4 mr-2" />
              Save
            </Button>
          </div>
        </div>
      </div>
    </>
  );
}
