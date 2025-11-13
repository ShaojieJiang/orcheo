import React, { Component, type ErrorInfo, type ReactNode } from "react";

import { Button } from "@/design-system/ui/button";

interface TraceViewerErrorBoundaryProps {
  children: ReactNode;
  onReset?: () => void;
  resetKey?: string | null;
}

interface TraceViewerErrorBoundaryState {
  hasError: boolean;
}

export class TraceViewerErrorBoundary extends Component<
  TraceViewerErrorBoundaryProps,
  TraceViewerErrorBoundaryState
> {
  public state: TraceViewerErrorBoundaryState = {
    hasError: false,
  };

  public static getDerivedStateFromError(): TraceViewerErrorBoundaryState {
    return { hasError: true };
  }

  public componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("TraceViewerErrorBoundary caught an error", error, info);
  }

  public componentDidUpdate(prevProps: TraceViewerErrorBoundaryProps) {
    if (prevProps.resetKey !== this.props.resetKey && this.state.hasError) {
      this.reset();
    }
  }

  private reset() {
    this.setState({ hasError: false });
    this.props.onReset?.();
  }

  public render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div className="flex h-full flex-col items-center justify-center gap-4 p-6 text-center">
          <div className="space-y-2">
            <h3 className="text-base font-semibold">Something went wrong</h3>
            <p className="text-muted-foreground text-sm">
              We were unable to render the trace details. Try again, and if the
              problem persists please reload the execution.
            </p>
          </div>
          <Button size="sm" variant="outline" onClick={() => this.reset()}>
            Try again
          </Button>
        </div>
      );
    }

    return this.props.children;
  }
}

export default TraceViewerErrorBoundary;
