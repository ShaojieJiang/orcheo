import { useCallback } from "react";
import type { DragEvent as ReactDragEvent } from "react";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/design-system/ui/tabs";
import { Badge } from "@/design-system/ui/badge";
import { Code, FileJson, GripVertical, Table } from "lucide-react";
import { LiveDataUnavailable } from "./live-data-unavailable";
import { writeSchemaFieldDragData } from "../schema-dnd";
import type { SchemaField } from "./types";

interface InputPanelProps {
  inputViewMode: string;
  onInputViewModeChange: (value: string) => void;
  useLiveData: boolean;
  hasRuntime: boolean;
  hasLiveInputs: boolean;
  liveInputs: unknown;
  hasUpstreamConnections: boolean;
  upstreamInputs: Record<string, unknown>;
  schemaFields: SchemaField[];
}

export function InputPanel({
  inputViewMode,
  onInputViewModeChange,
  useLiveData,
  hasRuntime,
  hasLiveInputs,
  liveInputs,
  hasUpstreamConnections,
  upstreamInputs,
  schemaFields,
}: InputPanelProps) {
  const handleDragStart = useCallback(
    (event: ReactDragEvent<HTMLDivElement>, field: SchemaField) => {
      writeSchemaFieldDragData(event.dataTransfer, field);
    },
    [],
  );

  const handleDragEnd = useCallback(() => {
    // Placeholder for future drag end logic (e.g., analytics or visual feedback).
  }, []);

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border">
        <Tabs
          defaultValue={inputViewMode}
          onValueChange={onInputViewModeChange}
        >
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
                  <LiveDataUnavailable
                    label="Live Input"
                    hasRuntime={hasRuntime}
                  />
                )
              ) : hasUpstreamConnections ? (
                Object.keys(upstreamInputs).length > 0 ? (
                  <pre className="font-mono text-sm whitespace-pre overflow-auto rounded-md bg-muted p-4 h-full">
                    {JSON.stringify(upstreamInputs, null, 2)}
                  </pre>
                ) : (
                  <div className="flex items-center justify-center h-full">
                    <div className="text-center">
                      <Badge variant="outline" className="mb-2">
                        No Outputs
                      </Badge>
                      <p className="text-sm text-muted-foreground">
                        Connected nodes have not produced outputs yet.
                        <br />
                        Run the workflow to see input data.
                      </p>
                    </div>
                  </div>
                )
              ) : (
                <div className="flex items-center justify-center h-full">
                  <div className="text-center">
                    <Badge variant="outline" className="mb-2">
                      No Connections
                    </Badge>
                    <p className="text-sm text-muted-foreground">
                      This node has no incoming connections.
                      <br />
                      Connect nodes to see their outputs here.
                    </p>
                  </div>
                </div>
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
                {hasUpstreamConnections ? (
                  schemaFields.length > 0 ? (
                    <div className="space-y-2">
                      {schemaFields.map((field) => (
                        <div
                          key={field.path}
                          className="flex items-center justify-between p-2 bg-background rounded border border-border hover:border-primary/50 cursor-grab"
                          draggable
                          onDragStart={(event) => handleDragStart(event, field)}
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
                  ) : (
                    <div className="flex items-center justify-center h-full">
                      <div className="text-center">
                        <Badge variant="outline" className="mb-2">
                          No Schema
                        </Badge>
                        <p className="text-sm text-muted-foreground">
                          Connected nodes have not produced outputs yet.
                          <br />
                          Run the workflow to see the schema.
                        </p>
                      </div>
                    </div>
                  )
                ) : (
                  <div className="flex items-center justify-center h-full">
                    <div className="text-center">
                      <Badge variant="outline" className="mb-2">
                        No Connections
                      </Badge>
                      <p className="text-sm text-muted-foreground">
                        This node has no incoming connections.
                        <br />
                        Connect nodes to see their output schema here.
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
