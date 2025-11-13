import { TraceViewer } from "@/components/agent-prism/TraceViewer/TraceViewer";
import { TraceViewerPlaceholder } from "@/components/agent-prism/TraceViewer/TraceViewerPlaceholder";
import { TraceViewerErrorBoundary } from "@/components/agent-prism/TraceViewer/TraceViewerErrorBoundary";
import { Button } from "@/design-system/ui/button";

import type { TraceViewerData } from "@/components/agent-prism/TraceViewer/TraceViewer";

interface TraceTabContentProps {
  activeExecutionId: string | null;
  viewerData: TraceViewerData | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}

export function TraceTabContent({
  activeExecutionId,
  viewerData,
  loading,
  error,
  onRetry,
}: TraceTabContentProps) {
  if (!activeExecutionId) {
    return (
      <div className="flex h-full items-center justify-center p-4">
        <TraceViewerPlaceholder title="Select an execution to view its trace." />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 p-6 text-center">
        <p className="text-muted-foreground text-sm">
          {error || "Unable to load trace details."}
        </p>
        <Button variant="outline" size="sm" onClick={onRetry}>
          Retry loading trace
        </Button>
      </div>
    );
  }

  if (!viewerData) {
    return (
      <div className="flex h-full items-center justify-center p-4">
        <TraceViewerPlaceholder
          title={
            loading
              ? "Loading trace metadata..."
              : "Trace data will appear here once spans are recorded."
          }
        />
      </div>
    );
  }

  if (viewerData.spans.length === 0) {
    return (
      <div className="flex h-full items-center justify-center p-4">
        <TraceViewerPlaceholder
          title={
            loading
              ? "Loading trace spans..."
              : "Trace spans will appear here once they are recorded."
          }
        />
      </div>
    );
  }

  return (
    <div className="h-full overflow-hidden">
      <TraceViewerErrorBoundary resetKey={viewerData.traceRecord.id}>
        <TraceViewer
          data={[viewerData]}
          spanCardViewOptions={{ expandButton: "inside" }}
        />
      </TraceViewerErrorBoundary>
    </div>
  );
}

export type { TraceTabContentProps };
