import { ExecutionState } from "./time-travel-types";

interface StateDetailsProps {
  state?: ExecutionState;
}

export function TimeTravelStateDetails({ state }: StateDetailsProps) {
  if (!state) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-muted-foreground">Select a state to view details</p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-hidden flex flex-col">
      <div className="p-2 bg-muted/30 border-b border-border">
        <h4 className="text-sm font-medium">Node: {state.nodeName}</h4>
      </div>
      <div className="flex-1 overflow-auto p-4">
        <div className="space-y-4">
          <div>
            <h5 className="text-sm font-medium mb-2">Input Data</h5>
            <div className="bg-muted p-3 rounded-md overflow-auto max-h-[200px]">
              <pre className="text-xs">
                {state.inputData
                  ? JSON.stringify(state.inputData, null, 2)
                  : "No input data"}
              </pre>
            </div>
          </div>

          {state.state !== "running" && (
            <div>
              <h5 className="text-sm font-medium mb-2">Output Data</h5>
              <div className="bg-muted p-3 rounded-md overflow-auto max-h-[200px]">
                <pre className="text-xs">
                  {state.outputData
                    ? JSON.stringify(state.outputData, null, 2)
                    : state.error
                      ? `Error: ${state.error}`
                      : "No output data"}
                </pre>
              </div>
            </div>
          )}

          {state.error && (
            <div>
              <h5 className="text-sm font-medium mb-2 text-red-500">Error</h5>
              <div className="bg-red-50 dark:bg-red-900/20 p-3 rounded-md overflow-auto max-h-[200px] border border-red-200 dark:border-red-800">
                <pre className="text-xs text-red-700 dark:text-red-300">
                  {state.error}
                </pre>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
