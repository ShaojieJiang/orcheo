import {
  Loader2,
  Plus,
  Puzzle,
  Trash2,
  RefreshCcw,
  CalendarClock,
  AlertTriangle,
  CheckCircle2,
} from "lucide-react";

import { cn } from "@/lib/utils";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/design-system/ui/card";
import { Button } from "@/design-system/ui/button";
import { Badge } from "@/design-system/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/design-system/ui/alert";

import CredentialsVault, {
  type Credential,
  type CredentialInput,
} from "../dialogs/credentials-vault";
import type { ValidationError } from "../canvas/connection-validator";

export interface SubworkflowTemplate {
  id: string;
  name: string;
  description: string;
  tags: string[];
  version: string;
  status: "stable" | "beta" | "deprecated";
  usageCount: number;
  lastUpdated: string;
}

export interface WorkflowGovernancePanelProps {
  credentials: Credential[];
  onAddCredential: (credential: CredentialInput) => void;
  onDeleteCredential: (id: string) => void;
  subworkflows: SubworkflowTemplate[];
  onCreateSubworkflow: () => void;
  onInsertSubworkflow: (subworkflow: SubworkflowTemplate) => void;
  onDeleteSubworkflow: (id: string) => void;
  validationErrors: ValidationError[];
  onRunValidation: () => void;
  onDismissValidation: (id: string) => void;
  onFixValidation: (error: ValidationError) => void;
  isValidating: boolean;
  lastValidationRun?: string | null;
  className?: string;
}

const STATUS_LABEL: Record<SubworkflowTemplate["status"], string> = {
  stable: "Stable",
  beta: "Beta",
  deprecated: "Deprecated",
};

export default function WorkflowGovernancePanel({
  credentials,
  onAddCredential,
  onDeleteCredential,
  subworkflows,
  onCreateSubworkflow,
  onInsertSubworkflow,
  onDeleteSubworkflow,
  validationErrors,
  onRunValidation,
  onDismissValidation,
  onFixValidation,
  isValidating,
  lastValidationRun,
  className,
}: WorkflowGovernancePanelProps) {
  const renderSubworkflowStatus = (status: SubworkflowTemplate["status"]) => {
    if (status === "stable") {
      return <Badge variant="secondary">{STATUS_LABEL[status]}</Badge>;
    }

    if (status === "deprecated") {
      return (
        <Badge
          variant="destructive"
          className="bg-destructive/10 text-destructive"
        >
          {STATUS_LABEL[status]}
        </Badge>
      );
    }

    return <Badge variant="outline">{STATUS_LABEL[status]}</Badge>;
  };

  return (
    <div className={cn("space-y-6", className)}>
      <CredentialsVault
        credentials={credentials}
        onAddCredential={onAddCredential}
        onDeleteCredential={onDeleteCredential}
      />

      <Card>
        <CardHeader className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
          <div>
            <CardTitle>Reusable Sub-workflows</CardTitle>
            <CardDescription>
              Curate reusable workflow templates to accelerate delivery across
              teams.
            </CardDescription>
          </div>
          <Button onClick={onCreateSubworkflow} className="mt-2 md:mt-0">
            <Plus className="mr-2 h-4 w-4" />
            New sub-workflow
          </Button>
        </CardHeader>
        <CardContent>
          {subworkflows.length === 0 ? (
            <div className="rounded-lg border border-dashed border-muted-foreground/50 p-10 text-center text-sm text-muted-foreground">
              No reusable sub-workflows yet. Create your first template to share
              best practices with your team.
            </div>
          ) : (
            <div className="grid gap-4 lg:grid-cols-2">
              {subworkflows.map((subworkflow) => (
                <div
                  key={subworkflow.id}
                  className="flex h-full flex-col justify-between rounded-lg border border-border bg-muted/30 p-5"
                >
                  <div className="space-y-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <h3 className="text-base font-semibold leading-tight">
                          {subworkflow.name}
                        </h3>
                        <p className="mt-1 text-sm text-muted-foreground">
                          {subworkflow.description}
                        </p>
                      </div>
                      {renderSubworkflowStatus(subworkflow.status)}
                    </div>

                    <div className="flex flex-wrap gap-2">
                      {subworkflow.tags.map((tag) => (
                        <Badge
                          key={`${subworkflow.id}-${tag}`}
                          variant="outline"
                        >
                          {tag}
                        </Badge>
                      ))}
                    </div>
                  </div>

                  <div className="mt-6 space-y-3 text-sm text-muted-foreground">
                    <div className="flex items-center gap-2">
                      <Puzzle className="h-4 w-4" />
                      {subworkflow.usageCount}{" "}
                      {subworkflow.usageCount === 1 ? "workflow" : "workflows"}{" "}
                      rely on this template
                    </div>
                    <div className="flex items-center gap-2">
                      <CalendarClock className="h-4 w-4" />
                      Updated{" "}
                      {new Date(subworkflow.lastUpdated).toLocaleString()}
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant="secondary" className="uppercase">
                        v{subworkflow.version}
                      </Badge>
                      Versioned for consistency
                    </div>
                  </div>

                  <div className="mt-6 flex flex-wrap justify-end gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => onInsertSubworkflow(subworkflow)}
                    >
                      Insert into canvas
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-destructive hover:text-destructive"
                      onClick={() => onDeleteSubworkflow(subworkflow.id)}
                    >
                      <Trash2 className="mr-2 h-4 w-4" />
                      Remove
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

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
                All automated checks have passed. You can publish with
                confidence.
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
    </div>
  );
}
