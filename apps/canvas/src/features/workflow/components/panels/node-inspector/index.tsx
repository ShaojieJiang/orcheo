import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { OnMount } from "@monaco-editor/react";
import type { editor as MonacoEditor } from "monaco-editor";
import {
  collectUpstreamOutputs,
  findUpstreamNodes,
  hasIncomingConnections,
  mergeRuntimeSummaries,
} from "@features/workflow/lib/graph-utils";
import { DEFAULT_PYTHON_CODE } from "@features/workflow/lib/python-node";
import { NodeInspectorLayout } from "./node-inspector-layout";
import { useNodeTester } from "./use-node-tester";
import { buildSchemaFields } from "./schema-fields";
import type { NodeInspectorProps, NodeRuntimeCacheEntry } from "./types";
import {
  extractPythonCode,
  formatUpdatedAt,
  getOutputDisplay,
  getSemanticType,
  isRecord,
} from "./utils";

export default function NodeInspector({
  node,
  nodes = [],
  edges = [],
  onClose,
  onSave,
  runtimeCache,
  onCacheRuntime,
  className,
}: NodeInspectorProps) {
  const runtimeCandidate = node
    ? (node.data as Record<string, unknown>)["runtime"]
    : undefined;
  const runtimeFromNode = isRecord(runtimeCandidate)
    ? (runtimeCandidate as NodeRuntimeCacheEntry)
    : undefined;
  const cachedRuntime = node ? runtimeCache?.[node.id] : undefined;
  const runtime = mergeRuntimeSummaries(runtimeFromNode, cachedRuntime) ?? null;
  const hasRuntime = Boolean(runtime);

  const [useLiveData, setUseLiveData] = useState(hasRuntime);
  const [draftData, setDraftData] = useState<Record<string, unknown>>(() =>
    node?.data ? { ...(node.data as Record<string, unknown>) } : {},
  );
  const [pythonCode, setPythonCode] = useState(() => extractPythonCode(node));
  const [inputViewMode, setInputViewMode] = useState("input-json");
  const [outputViewMode, setOutputViewMode] = useState("output-json");

  const previouslyHadRuntimeRef = useRef(hasRuntime);
  const editorKeydownDisposableRef = useRef<MonacoEditor.IDisposable | null>(
    null,
  );
  const handleSaveRef = useRef<() => void>();

  const upstreamNodes = useMemo(() => {
    if (!node) return [];
    return findUpstreamNodes(node.id, nodes, edges);
  }, [node, nodes, edges]);

  const upstreamOutputs = useMemo(() => {
    return collectUpstreamOutputs(upstreamNodes, runtimeCache);
  }, [runtimeCache, upstreamNodes]);

  const hasUpstreamConnections = useMemo(() => {
    if (!node) return false;
    return hasIncomingConnections(node.id, edges);
  }, [node, edges]);

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
    if (!node) {
      return;
    }
    if (isPythonNode) {
      setPythonCode(extractPythonCode(node));
    }
    setDraftData(
      node.data ? { ...(node.data as Record<string, unknown>) } : {},
    );
  }, [isPythonNode, node]);

  useEffect(() => {
    return () => {
      editorKeydownDisposableRef.current?.dispose();
    };
  }, []);

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

  const liveInputs = runtime?.inputs;
  const hasLiveInputs = liveInputs !== undefined;
  const { outputDisplay, hasLiveOutputs } = useMemo(() => {
    return getOutputDisplay(runtime);
  }, [runtime]);
  const formattedUpdatedAt = useMemo(
    () => formatUpdatedAt(runtime?.updatedAt),
    [runtime?.updatedAt],
  );

  const schemaFields = useMemo(() => {
    return buildSchemaFields(
      hasUpstreamConnections ? upstreamOutputs : undefined,
    );
  }, [hasUpstreamConnections, upstreamOutputs]);

  const backendType = useMemo(() => {
    if (typeof draftData?.backendType === "string") {
      return draftData.backendType as string;
    }
    return typeof node?.data?.backendType === "string"
      ? (node.data.backendType as string)
      : null;
  }, [draftData, node]);

  const { isTestingNode, testResult, testError, handleTestNode } =
    useNodeTester({
      node,
      backendType,
      draftData,
      liveInputs,
      upstreamOutputs,
      useLiveData,
      onCacheRuntime,
    });

  if (!node) {
    return null;
  }

  const nodeLabelCandidate = node.data?.label;
  const nodeLabel =
    typeof nodeLabelCandidate === "string" && nodeLabelCandidate.length > 0
      ? nodeLabelCandidate
      : (node.type ?? "");
  const formattedSemanticType = semanticType
    ? `${semanticType.charAt(0).toUpperCase()}${semanticType.slice(1)}`
    : null;

  return (
    <NodeInspectorLayout
      node={node}
      className={className}
      nodeLabel={nodeLabel}
      formattedSemanticType={formattedSemanticType}
      onClose={onClose}
      inputViewMode={inputViewMode}
      onInputViewModeChange={setInputViewMode}
      useLiveData={useLiveData}
      hasRuntime={hasRuntime}
      hasLiveInputs={hasLiveInputs}
      liveInputs={liveInputs}
      hasUpstreamConnections={hasUpstreamConnections}
      upstreamOutputs={upstreamOutputs}
      schemaFields={schemaFields}
      backendType={backendType}
      isPythonNode={isPythonNode}
      draftData={draftData}
      setDraftData={setDraftData}
      pythonCode={pythonCode}
      onPythonCodeChange={setPythonCode}
      onEditorMount={handleEditorMount}
      outputViewMode={outputViewMode}
      onOutputViewModeChange={setOutputViewMode}
      onToggleLiveData={setUseLiveData}
      runtime={runtime}
      formattedUpdatedAt={formattedUpdatedAt}
      testResult={testResult}
      testError={testError}
      hasLiveOutputs={hasLiveOutputs}
      outputDisplay={outputDisplay}
      onTestNode={handleTestNode}
      isTestingNode={isTestingNode}
      onSave={handleSave}
    />
  );
}
