import React from "react";

import { Button } from "@/design-system/ui/button";
import { Separator } from "@/design-system/ui/separator";
import WorkflowHistory from "@features/workflow/components/panels/workflow-history";

export interface SettingsTabContentProps {
  workflowName: string;
  workflowDescription: string;
  workflowTags: string[];
  onWorkflowNameChange: (value: string) => void;
  onWorkflowDescriptionChange: (value: string) => void;
  onTagsChange: (value: string) => void;
  workflowVersions: Array<{ version: string; createdAt: string }>;
  onRestoreVersion: (version: { version: string; createdAt: string }) => void;
  onSaveWorkflow: () => void;
}

export function SettingsTabContent({
  workflowName,
  workflowDescription,
  workflowTags,
  onWorkflowNameChange,
  onWorkflowDescriptionChange,
  onTagsChange,
  workflowVersions,
  onRestoreVersion,
  onSaveWorkflow,
}: SettingsTabContentProps) {
  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <div>
        <h2 className="text-xl font-bold mb-4">Workflow Settings</h2>
        <div className="space-y-4">
          <div className="grid gap-2">
            <label className="text-sm font-medium">Workflow Name</label>
            <input
              type="text"
              className="border border-border rounded-md px-3 py-2 bg-background"
              value={workflowName}
              onChange={(event) => onWorkflowNameChange(event.target.value)}
            />
          </div>
          <div className="grid gap-2">
            <label className="text-sm font-medium">Description</label>
            <textarea
              className="border border-border rounded-md px-3 py-2 bg-background"
              rows={3}
              value={workflowDescription}
              onChange={(event) =>
                onWorkflowDescriptionChange(event.target.value)
              }
            />
          </div>
          <div className="grid gap-2">
            <label className="text-sm font-medium">Tags</label>
            <input
              type="text"
              className="border border-border rounded-md px-3 py-2 bg-background"
              value={workflowTags.join(", ")}
              onChange={(event) => onTagsChange(event.target.value)}
            />

            <p className="text-xs text-muted-foreground">
              Separate tags with commas
            </p>
          </div>
        </div>
      </div>

      <Separator />

      <div>
        <h2 className="text-xl font-bold mb-4">Execution Settings</h2>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <label className="text-sm font-medium">Timeout (seconds)</label>
              <p className="text-xs text-muted-foreground">
                Maximum execution time for the workflow
              </p>
            </div>
            <input
              type="number"
              className="border border-border rounded-md px-3 py-2 bg-background w-24"
              defaultValue="300"
            />
          </div>
          <div className="flex items-center justify-between">
            <div>
              <label className="text-sm font-medium">Retry on Failure</label>
              <p className="text-xs text-muted-foreground">
                Automatically retry the workflow if it fails
              </p>
            </div>
            <div className="flex items-center h-6">
              <input type="checkbox" className="h-4 w-4" defaultChecked />
            </div>
          </div>
          <div className="flex items-center justify-between">
            <div>
              <label className="text-sm font-medium">Maximum Retries</label>
              <p className="text-xs text-muted-foreground">
                Number of retry attempts before giving up
              </p>
            </div>
            <input
              type="number"
              className="border border-border rounded-md px-3 py-2 bg-background w-24"
              defaultValue="3"
            />
          </div>
        </div>
      </div>

      <Separator />

      <div>
        <h2 className="text-xl font-bold mb-4">Notifications</h2>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <label className="text-sm font-medium">Email Notifications</label>
              <p className="text-xs text-muted-foreground">
                Send email when workflow fails
              </p>
            </div>
            <div className="flex items-center h-6">
              <input type="checkbox" className="h-4 w-4" defaultChecked />
            </div>
          </div>
          <div className="flex items-center justify-between">
            <div>
              <label className="text-sm font-medium">Slack Notifications</label>
              <p className="text-xs text-muted-foreground">
                Send Slack message when workflow completes
              </p>
            </div>
            <div className="flex items-center h-6">
              <input type="checkbox" className="h-4 w-4" />
            </div>
          </div>
        </div>
      </div>

      <Separator />

      <WorkflowHistory
        versions={workflowVersions}
        currentVersion={workflowVersions.at(-1)?.version}
        onRestoreVersion={onRestoreVersion}
      />

      <div className="flex justify-end gap-2">
        <Button variant="outline">Cancel</Button>
        <Button onClick={onSaveWorkflow}>Save Settings</Button>
      </div>
    </div>
  );
}
