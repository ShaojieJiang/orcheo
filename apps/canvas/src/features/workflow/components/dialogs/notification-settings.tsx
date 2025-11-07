import React, { useState } from "react";
import { Button } from "@/design-system/ui/button";
import { Separator } from "@/design-system/ui/separator";
import { Bell, Plus } from "lucide-react";
import { cn } from "@/lib/utils";
import AddNotificationChannelDialog from "./add-notification-channel-dialog";
import NotificationChannelCard from "./notification-channel-card";
import {
  NotificationEventKey,
  NotificationSettingsProps,
  NewNotificationChannel,
} from "./notification-settings.types";

export default function NotificationSettings({
  channels = [],
  onAddChannel,
  onUpdateChannel,
  onDeleteChannel,
  className,
}: NotificationSettingsProps) {
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);

  const handleAddChannel = (channel: NewNotificationChannel) => {
    onAddChannel?.(channel);
  };

  const handleToggleEvent = (
    channelId: string,
    event: NotificationEventKey,
    value: boolean,
  ) => {
    const channel = channels.find((c) => c.id === channelId);
    if (channel && onUpdateChannel) {
      onUpdateChannel(channelId, {
        events: {
          ...channel.events,
          [event]: value,
        },
      });
    }
  };

  const handleToggleEnabled = (channelId: string, enabled: boolean) => {
    onUpdateChannel?.(channelId, { enabled });
  };

  const handleDeleteChannel = (channelId: string) => {
    onDeleteChannel?.(channelId);
  };

  const renderEmptyState = () => (
    <div className="text-center py-8 border border-dashed rounded-lg">
      <Bell className="h-10 w-10 mx-auto text-muted-foreground mb-4" />
      <h3 className="text-lg font-medium mb-2">No notification channels</h3>
      <p className="text-sm text-muted-foreground mb-4">
        Add a notification channel to get alerts about workflow events
      </p>
      <Button onClick={() => setIsAddDialogOpen(true)}>
        <Plus className="h-4 w-4 mr-2" />
        Add Channel
      </Button>
    </div>
  );

  return (
    <div className={cn("space-y-6", className)}>
      <div className="flex justify-between items-center">
        <div>
          <h3 className="text-lg font-medium flex items-center gap-2">
            <Bell className="h-5 w-5" />
            Notification Settings
          </h3>
          <p className="text-sm text-muted-foreground">
            Configure how you want to be notified about workflow events
          </p>
        </div>
        <Button onClick={() => setIsAddDialogOpen(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Add Channel
        </Button>
      </div>

      <Separator />

      {channels.length === 0 ? (
        renderEmptyState()
      ) : (
        <div className="grid gap-6 md:grid-cols-2">
          {channels.map((channel) => (
            <NotificationChannelCard
              key={channel.id}
              channel={channel}
              onToggleEnabled={handleToggleEnabled}
              onToggleEvent={handleToggleEvent}
              onDeleteChannel={handleDeleteChannel}
            />
          ))}
        </div>
      )}

      <AddNotificationChannelDialog
        open={isAddDialogOpen}
        onOpenChange={setIsAddDialogOpen}
        onAddChannel={handleAddChannel}
      />
    </div>
  );
}
