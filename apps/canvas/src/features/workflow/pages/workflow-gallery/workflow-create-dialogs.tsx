import { ChangeEvent } from "react";
import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/design-system/ui/dialog";
import { Label } from "@/design-system/ui/label";
import { FolderPlus, Plus } from "lucide-react";

interface WorkflowCreateFolderDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  folderName: string;
  onFolderNameChange: (value: string) => void;
  onCreateFolder: () => void;
}

export const WorkflowCreateFolderDialog = ({
  open,
  onOpenChange,
  folderName,
  onFolderNameChange,
  onCreateFolder,
}: WorkflowCreateFolderDialogProps) => (
  <Dialog open={open} onOpenChange={onOpenChange}>
    <DialogTrigger asChild>
      <Button variant="outline">
        <FolderPlus className="mr-2 h-4 w-4" />
        New Folder
      </Button>
    </DialogTrigger>
    <DialogContent>
      <DialogHeader>
        <DialogTitle>Create New Folder</DialogTitle>
        <DialogDescription>Enter a name for your new folder.</DialogDescription>
      </DialogHeader>
      <div className="py-4">
        <Label htmlFor="folder-name">Folder Name</Label>
        <Input
          id="folder-name"
          value={folderName}
          onChange={(event: ChangeEvent<HTMLInputElement>) =>
            onFolderNameChange(event.target.value)
          }
          placeholder="My Workflows"
          className="mt-2"
        />
      </div>
      <DialogFooter>
        <Button variant="outline" onClick={() => onOpenChange(false)}>
          Cancel
        </Button>
        <Button onClick={onCreateFolder}>Create Folder</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
);

interface WorkflowCreateWorkflowDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  workflowName: string;
  onWorkflowNameChange: (value: string) => void;
  onCreateWorkflow: () => void;
}

export const WorkflowCreateWorkflowDialog = ({
  open,
  onOpenChange,
  workflowName,
  onWorkflowNameChange,
  onCreateWorkflow,
}: WorkflowCreateWorkflowDialogProps) => (
  <Dialog open={open} onOpenChange={onOpenChange}>
    <DialogTrigger asChild>
      <Button>
        <Plus className="mr-2 h-4 w-4" />
        Create Workflow
      </Button>
    </DialogTrigger>
    <DialogContent>
      <DialogHeader>
        <DialogTitle>Create New Workflow</DialogTitle>
        <DialogDescription>
          Enter a name for your new workflow.
        </DialogDescription>
      </DialogHeader>
      <div className="py-4">
        <Label htmlFor="workflow-name">Workflow Name</Label>
        <Input
          id="workflow-name"
          value={workflowName}
          onChange={(event: ChangeEvent<HTMLInputElement>) =>
            onWorkflowNameChange(event.target.value)
          }
          placeholder="My New Workflow"
          className="mt-2"
        />
      </div>
      <DialogFooter>
        <Button variant="outline" onClick={() => onOpenChange(false)}>
          Cancel
        </Button>
        <Button onClick={onCreateWorkflow}>Create &amp; Open</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
);
