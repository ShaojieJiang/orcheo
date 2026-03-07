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
import { FolderPlus } from "lucide-react";

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
