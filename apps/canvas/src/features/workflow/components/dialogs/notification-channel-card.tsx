import React from "react";
import { Button } from "@/design-system/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/design-system/ui/card";
import { Switch } from "@/design-system/ui/switch";
import { Bell, Mail, MessageSquare, Trash, Webhook } from "lucide-react";
import {
  NotificationChannel,
  NotificationEventKey,
} from "./notification-settings.types";
import NotificationEventToggles from "./notification-event-toggles";

interface NotificationChannelCardProps {
  channel: NotificationChannel;
  onToggleEnabled?: (id: string, enabled: boolean) => void;
  onToggleEvent?: (
    id: string,
    event: NotificationEventKey,
    value: boolean,
  ) => void;
  onDeleteChannel?: (id: string) => void;
}

const getChannelIcon = (type: NotificationChannel["type"]) => {
  switch (type) {
    case "email":
      return <Mail className="h-5 w-5" />;
    case "slack":
      return <MessageSquare className="h-5 w-5" />;
    case "webhook":
      return <Webhook className="h-5 w-5" />;
    default:
      return <Bell className="h-5 w-5" />;
  }
};

const NotificationChannelCard: React.FC<NotificationChannelCardProps> = ({
  channel,
  onToggleEnabled,
  onToggleEvent,
  onDeleteChannel,
}) => {
  const handleToggleEvent = (event: NotificationEventKey, value: boolean) => {
    onToggleEvent?.(channel.id, event, value);
  };

  return (
    <Card className={!channel.enabled ? "opacity-60" : ""}>
      <CardHeader className="pb-2">
        <div className="flex justify-between items-start">
          <div className="flex items-center gap-2">
            {getChannelIcon(channel.type)}
            <CardTitle className="text-lg">{channel.name}</CardTitle>
          </div>
          <Switch
            checked={channel.enabled}
            onCheckedChange={(checked) =>
              onToggleEnabled?.(channel.id, checked)
            }
          />
        </div>
        <CardDescription>
          {channel.type === "email" && (
            <span>Email to {channel.config.recipients?.join(", ")}</span>
          )}
          {channel.type === "slack" && (
            <span>Slack channel {channel.config.slackChannel}</span>
          )}
          {channel.type === "webhook" && (
            <span className="truncate block">
              Webhook: {channel.config.webhookUrl}
            </span>
          )}
        </CardDescription>
      </CardHeader>
      <CardContent className="pb-2">
        <NotificationEventToggles
          idPrefix={channel.id}
          events={channel.events}
          onToggle={handleToggleEvent}
          disabled={!channel.enabled}
          size="sm"
        />
      </CardContent>
      <CardFooter className="pt-2">
        <Button
          variant="outline"
          size="sm"
          className="text-destructive hover:text-destructive"
          onClick={() => onDeleteChannel?.(channel.id)}
        >
          <Trash className="h-3 w-3 mr-1" />
          Remove
        </Button>
      </CardFooter>
    </Card>
  );
};

export default NotificationChannelCard;
