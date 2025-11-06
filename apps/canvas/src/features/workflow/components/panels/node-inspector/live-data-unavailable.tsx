import { Badge } from "@/design-system/ui/badge";

interface LiveDataUnavailableProps {
  label: string;
  hasRuntime: boolean;
}

export function LiveDataUnavailable({
  label,
  hasRuntime,
}: LiveDataUnavailableProps) {
  return (
    <div className="flex items-center justify-center h-full">
      <div className="text-center">
        <Badge variant="outline" className="mb-2">
          {label}
        </Badge>
        <p className="text-sm text-muted-foreground">
          {hasRuntime
            ? "No live data captured for this node yet."
            : "Run the workflow to capture live data."}
        </p>
      </div>
    </div>
  );
}
