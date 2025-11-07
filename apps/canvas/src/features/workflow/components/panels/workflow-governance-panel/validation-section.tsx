import { Alert, AlertDescription, AlertTitle } from "@/design-system/ui/alert";
import { Button } from "@/design-system/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/design-system/ui/card";
import { AlertTriangle, CheckCircle2, Loader2, RefreshCcw } from "lucide-react";

import type { WorkflowGovernancePanelProps } from "./types";

type ValidationSectionProps = Pick<
  WorkflowGovernancePanelProps,
  | "validationErrors"
  | "isValidating"
  | "onRunValidation"
  | "onDismissValidation"
  | "onFixValidation"
  | "lastValidationRun"
>;

export function ValidationSection({
  validationErrors,
  isValidating,
  onRunValidation,
  onDismissValidation,
  onFixValidation,
  lastValidationRun,
}: ValidationSectionProps) {
  return (
    <Card>
      <CardHeader className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
        <div>
          <CardTitle>Publish-time validation</CardTitle>
          <CardDescription>
            Run automated checks to confirm your workflow is ready for
            production deployment.
          </CardDescription>
        </div>
        <Button
          onClick={onRunValidation}
          disabled={isValidating}
          variant="secondary"
        >
          {isValidating ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Validating...
            </>
          ) : (
            <>
              <RefreshCcw className="mr-2 h-4 w-4" />
              Run validation
            </>
          )}
        </Button>
      </CardHeader>
      <CardContent className="space-y-4">
        {lastValidationRun && (
          <p className="text-xs text-muted-foreground">
            Last run {new Date(lastValidationRun).toLocaleString()}
          </p>
        )}

        {validationErrors.length === 0 ? (
          <Alert className="border-green-500/50 bg-green-500/5 text-green-900 dark:border-green-500/40 dark:bg-green-500/10 dark:text-green-200">
            <CheckCircle2 className="h-4 w-4" />
            <AlertTitle>Workflow is ready for publish</AlertTitle>
            <AlertDescription>
              All automated checks have passed. You can publish with confidence.
            </AlertDescription>
          </Alert>
        ) : (
          <div className="space-y-3">
            {validationErrors.map((error) => (
              <Alert key={error.id} variant="destructive" className="pr-3">
                <AlertTriangle className="h-4 w-4" />
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <AlertTitle className="capitalize">
                      {error.type.replace("_", " ")}
                    </AlertTitle>
                    <AlertDescription className="mt-1 text-sm">
                      {error.message}
                      {error.type === "connection" &&
                        error.sourceId &&
                        error.targetId && (
                          <span className="mt-1 block text-xs opacity-80">
                            {error.sourceId} → {error.targetId}
                          </span>
                        )}
                      {error.nodeName && (
                        <span className="mt-1 block text-xs opacity-80">
                          Node: {error.nodeName}
                        </span>
                      )}
                    </AlertDescription>
                  </div>
                  <div className="flex flex-shrink-0 flex-wrap justify-end gap-2">
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => onFixValidation(error)}
                    >
                      Review
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-destructive hover:text-destructive"
                      onClick={() => onDismissValidation(error.id)}
                    >
                      Dismiss
                    </Button>
                  </div>
                </div>
              </Alert>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
