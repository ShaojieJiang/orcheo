import "@features/workflow/components/trace/agent-prism/theme/theme.css";

import { formatDistanceToNow } from "date-fns";
import { RefreshCw } from "lucide-react";
import type { TraceSpan } from "@evilmartians/agent-prism-types";

import { Alert, AlertDescription, AlertTitle } from "@/design-system/ui/alert";
import { Button } from "@/design-system/ui/button";
import { Card, CardDescription, CardTitle } from "@/design-system/ui/card";
import { Skeleton } from "@/design-system/ui/skeleton";
import type { TraceViewerData } from "@features/workflow/components/trace/agent-prism";
import { TraceViewer } from "@features/workflow/components/trace/agent-prism";
import type { TraceEntryStatus } from "@features/workflow/pages/workflow-canvas/helpers/trace";
import type { TraceSpanMetadata } from "@features/workflow/pages/workflow-canvas/helpers/trace";

interface TraceSummary {
  spanCount: number;
  totalTokens: number;
}

const SUMMARY_CARD_CLASS = "px-3 py-2";
const SUMMARY_CARD_BODY_CLASS =
  "flex w-full items-center justify-between gap-3 text-sm";

export interface TraceTabContentProps {
  status: TraceEntryStatus;
  error?: string;
  viewerData: TraceViewerData[];
  activeViewer?: TraceViewerData;
  onRefresh: () => void;
  onSelectTrace?: (traceId: string) => void;
  summary?: TraceSummary;
  lastUpdatedAt?: string;
  isLive: boolean;
}

const formatTimestamp = (timestamp?: string): string => {
  if (!timestamp) {
    return "Never";
  }
  try {
    return formatDistanceToNow(new Date(timestamp), { addSuffix: true });
  } catch {
    return timestamp;
  }
};

const renderArtifactActions = (span: TraceSpan) => {
  const metadata = span.metadata as
    | (TraceSpanMetadata & {
        artifacts?: Array<{ id: string; downloadUrl?: string }>;
      })
    | undefined;
  const artifacts = metadata?.artifacts ?? [];
  if (artifacts.length === 0) {
    return null;
  }
  return (
    <div className="flex flex-wrap items-center gap-2">
      {artifacts.map((artifact) => (
        <Button
          key={artifact.id}
          size="sm"
          variant="outline"
          onClick={() => {
            if (artifact.downloadUrl) {
              window.open(
                artifact.downloadUrl,
                "_blank",
                "noopener,noreferrer",
              );
            }
          }}
        >
          Download {artifact.id}
        </Button>
      ))}
    </div>
  );
};

export function TraceTabContent({
  status,
  error,
  viewerData,
  activeViewer,
  onRefresh,
  onSelectTrace,
  summary,
  lastUpdatedAt,
  isLive,
}: TraceTabContentProps) {
  const isLoading = status === "loading" && !activeViewer;
  const hasData = viewerData.length > 0;

  return (
    <div className="flex h-full flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Execution trace</h2>
          <p className="text-sm text-muted-foreground">
            Inspect span hierarchy, metrics, and artifacts for the selected run.
          </p>
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={() => {
            void onRefresh();
          }}
        >
          <RefreshCw className="mr-2 size-4" /> Refresh
        </Button>
      </div>

      {summary && (
        <div className="grid gap-3 md:grid-cols-3">
          <Card className={SUMMARY_CARD_CLASS}>
            <div className={SUMMARY_CARD_BODY_CLASS}>
              <div className="space-y-0.5">
                <CardTitle className="text-xs font-semibold uppercase text-muted-foreground">
                  Spans
                </CardTitle>
                <CardDescription className="text-xs text-muted-foreground">
                  Recorded nodes and events
                </CardDescription>
              </div>
              <span className="text-sm font-semibold text-foreground">
                {summary.spanCount}
              </span>
            </div>
          </Card>
          <Card className={SUMMARY_CARD_CLASS}>
            <div className={SUMMARY_CARD_BODY_CLASS}>
              <div className="space-y-0.5">
                <CardTitle className="text-xs font-semibold uppercase text-muted-foreground">
                  Total tokens
                </CardTitle>
                <CardDescription className="text-xs text-muted-foreground">
                  Input + output consumption
                </CardDescription>
              </div>
              <span className="text-sm font-semibold text-foreground">
                {summary.totalTokens}
              </span>
            </div>
          </Card>
          <Card className={SUMMARY_CARD_CLASS}>
            <div className={SUMMARY_CARD_BODY_CLASS}>
              <div className="space-y-0.5">
                <CardTitle className="text-xs font-semibold uppercase text-muted-foreground">
                  Last update
                </CardTitle>
                <CardDescription className="text-xs text-muted-foreground">
                  {isLive ? "Live" : "Completed"}
                </CardDescription>
              </div>
              <span className="text-xs font-semibold text-foreground">
                {formatTimestamp(lastUpdatedAt)}
              </span>
            </div>
          </Card>
        </div>
      )}

      {error && (
        <Alert variant="destructive">
          <AlertTitle>Unable to load trace</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {isLoading && (
        <div className="space-y-4">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-72 w-full" />
        </div>
      )}

      {!isLoading && !hasData && !error && (
        <div className="flex flex-1 items-center justify-center rounded-md border border-dashed border-border text-sm text-muted-foreground">
          Trace data will appear here once spans are recorded.
        </div>
      )}

      {hasData && (
        <div className="min-h-0 flex-1 overflow-hidden rounded-lg border border-border bg-background">
          <TraceViewer
            data={viewerData}
            activeTraceId={activeViewer?.traceRecord.id}
            onTraceSelect={(trace) => {
              onSelectTrace?.(trace.id);
            }}
            detailsViewProps={{
              headerActions: renderArtifactActions,
            }}
          />
        </div>
      )}
    </div>
  );
}
