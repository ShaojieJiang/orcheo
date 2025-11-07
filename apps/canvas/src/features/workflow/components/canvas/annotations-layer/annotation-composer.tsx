import { Button } from "@/design-system/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/design-system/ui/avatar";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/design-system/ui/popover";
import { Textarea } from "@/design-system/ui/textarea";
import { Plus, X } from "lucide-react";

interface AnnotationComposerProps {
  isAdding: boolean;
  position: { x: number; y: number };
  content: string;
  onToggle: () => void;
  onContentChange: (value: string) => void;
  onSubmit: () => void;
  onCancel: () => void;
}

export function AnnotationComposer({
  isAdding,
  position,
  content,
  onToggle,
  onContentChange,
  onSubmit,
  onCancel,
}: AnnotationComposerProps) {
  return (
    <>
      <div className="absolute top-4 right-4 pointer-events-auto z-10">
        <Button
          variant={isAdding ? "default" : "outline"}
          size="sm"
          onClick={onToggle}
          className="gap-2"
        >
          {isAdding ? (
            <>
              <X className="h-4 w-4" />
              Cancel
            </>
          ) : (
            <>
              <Plus className="h-4 w-4" />
              Add Comment
            </>
          )}
        </Button>
      </div>

      {isAdding && (
        <div className="absolute top-16 right-4 bg-background border border-border rounded-md p-2 shadow-md pointer-events-auto">
          <p className="text-xs text-muted-foreground">
            Click anywhere on the canvas to add a comment
          </p>
        </div>
      )}

      {isAdding && (
        <Popover open>
          <PopoverTrigger asChild>
            <div
              className="absolute w-6 h-6 bg-primary rounded-full flex items-center justify-center cursor-pointer pointer-events-auto"
              style={{
                left: `${position.x}px`,
                top: `${position.y}px`,
                transform: "translate(-50%, -50%)",
              }}
            >
              <Plus className="h-4 w-4 text-primary-foreground" />
            </div>
          </PopoverTrigger>
          <PopoverContent
            className="w-80 pointer-events-auto"
            side="right"
            align="start"
          >
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Avatar className="h-6 w-6">
                  <AvatarImage src="https://avatar.vercel.sh/avery" />
                  <AvatarFallback>CU</AvatarFallback>
                </Avatar>
                <span className="text-sm font-medium">Current User</span>
              </div>
              <Textarea
                placeholder="Add your comment..."
                className="min-h-[100px]"
                value={content}
                onChange={(event) => onContentChange(event.target.value)}
                autoFocus
              />
              <div className="flex justify-end gap-2">
                <Button variant="ghost" size="sm" onClick={onCancel}>
                  Cancel
                </Button>
                <Button size="sm" onClick={onSubmit}>
                  Add Comment
                </Button>
              </div>
            </div>
          </PopoverContent>
        </Popover>
      )}
    </>
  );
}
