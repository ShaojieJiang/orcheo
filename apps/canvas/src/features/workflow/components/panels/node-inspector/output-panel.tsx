import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/design-system/ui/tabs";
import { Badge } from "@/design-system/ui/badge";
import { Button } from "@/design-system/ui/button";
import { Label } from "@/design-system/ui/label";
import { Switch } from "@/design-system/ui/switch";
import { Code, FileJson, RefreshCw, Table } from "lucide-react";
import { LiveDataUnavailable } from "./live-data-unavailable";
import type { NodeRuntimeCacheEntry } from "./types";

interface OutputPanelProps {
  outputViewMode: string;
  onOutputViewModeChange: (value: string) => void;
  useLiveData: boolean;
  onToggleLiveData: (value: boolean) => void;
  runtime: NodeRuntimeCacheEntry | null;
  formattedUpdatedAt: string | null;
  testResult: unknown;
  testError: string | null;
  hasRuntime: boolean;
  hasLiveOutputs: boolean;
  outputDisplay: unknown;
}

export function OutputPanel({
  outputViewMode,
  onOutputViewModeChange,
  useLiveData,
  onToggleLiveData,
  runtime,
  formattedUpdatedAt,
  testResult,
  testError,
  hasRuntime,
  hasLiveOutputs,
  outputDisplay,
}: OutputPanelProps) {
  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border">
        <div className="flex items-center justify-between">
          <Tabs
            defaultValue={outputViewMode}
            onValueChange={onOutputViewModeChange}
          >
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
                  onCheckedChange={onToggleLiveData}
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
            {testResult !== null ? (
              <div className="h-full">
                <div className="mb-2 flex items-center gap-2">
                  <Badge variant="secondary">Test Result</Badge>
                </div>
                <pre className="font-mono text-sm whitespace-pre overflow-auto rounded-md bg-muted p-4">
                  {JSON.stringify(testResult, null, 2)}
                </pre>
              </div>
            ) : testError !== null ? (
              <div className="h-full">
                <div className="mb-2 flex items-center gap-2">
                  <Badge variant="destructive">Test Error</Badge>
                </div>
                <pre className="font-mono text-sm whitespace-pre overflow-auto rounded-md bg-destructive/10 p-4 text-destructive">
                  {testError}
                </pre>
              </div>
            ) : useLiveData ? (
              hasLiveOutputs && outputDisplay !== undefined ? (
                <pre className="font-mono text-sm whitespace-pre overflow-auto rounded-md bg-muted p-4 h-full">
                  {JSON.stringify(outputDisplay, null, 2)}
                </pre>
              ) : (
                <LiveDataUnavailable
                  label="Live Output"
                  hasRuntime={hasRuntime}
                />
              )
            ) : (
              <div className="flex items-center justify-center h-full">
                <div className="text-center">
                  <Badge variant="outline" className="mb-2">
                    Sample Data
                  </Badge>
                  <p className="text-sm text-muted-foreground">
                    Click "Test Node" to execute this node in isolation
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
}
