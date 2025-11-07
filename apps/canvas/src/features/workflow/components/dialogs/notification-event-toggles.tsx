import React from "react";
import { Label } from "@/design-system/ui/label";
import { Switch } from "@/design-system/ui/switch";
import {
  AlertCircle,
  CheckCircle,
  Clock,
  Settings,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  NotificationChannelEvents,
  NotificationEventKey,
} from "./notification-settings.types";

const EVENT_OPTIONS: Array<{
  key: NotificationEventKey;
  label: string;
  icon: LucideIcon;
  colorClass: string;
}> = [
  {
    key: "workflowSuccess",
    label: "Workflow Success",
    icon: CheckCircle,
    colorClass: "text-green-500",
  },
  {
    key: "workflowFailure",
    label: "Workflow Failure",
    icon: AlertCircle,
    colorClass: "text-red-500",
  },
  {
    key: "workflowStart",
    label: "Workflow Start",
    icon: Clock,
    colorClass: "text-blue-500",
  },
  {
    key: "systemAlerts",
    label: "System Alerts",
    icon: Settings,
    colorClass: "text-amber-500",
  },
];

interface NotificationEventTogglesProps {
  idPrefix: string;
  events: NotificationChannelEvents;
  onToggle: (event: NotificationEventKey, value: boolean) => void;
  disabled?: boolean;
  size?: "sm" | "md";
  labelClassName?: string;
}

const NotificationEventToggles: React.FC<NotificationEventTogglesProps> = ({
  idPrefix,
  events,
  onToggle,
  disabled = false,
  size = "md",
  labelClassName,
}) => {
  const iconSize = size === "sm" ? "h-3 w-3" : "h-4 w-4";

  return (
    <div className="grid grid-cols-1 gap-3">
      {EVENT_OPTIONS.map(({ key, label, icon: Icon, colorClass }) => (
        <div key={key} className="flex items-center justify-between">
          <Label
            htmlFor={`${idPrefix}-${key}`}
            className={cn(
              "flex items-center gap-2",
              size === "sm" ? "text-sm" : undefined,
              labelClassName,
            )}
          >
            <Icon className={cn(iconSize, colorClass)} />
            {label}
          </Label>
          <Switch
            id={`${idPrefix}-${key}`}
            checked={events[key]}
            onCheckedChange={(checked) => onToggle(key, checked)}
            disabled={disabled}
          />
        </div>
      ))}
    </div>
  );
};

export default NotificationEventToggles;
