import React, { useEffect, useState } from "react";
import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";
import { Label } from "@/design-system/ui/label";
import { Separator } from "@/design-system/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/design-system/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/design-system/ui/dialog";
import {
  NewNotificationChannel,
  NotificationChannelType,
} from "./notification-settings.types";
import NotificationEventToggles from "./notification-event-toggles";

const configDefaults: Record<
  NotificationChannelType,
  NewNotificationChannel["config"]
> = {
  email: { recipients: [""], webhookUrl: undefined, slackChannel: undefined },
  slack: {
    slackChannel: "#alerts",
    recipients: undefined,
    webhookUrl: undefined,
  },
  webhook: { webhookUrl: "", recipients: undefined, slackChannel: undefined },
};

const defaultNewChannel: NewNotificationChannel = {
  type: "email",
  name: "",
  enabled: true,
  config: configDefaults.email,
  events: {
    workflowSuccess: false,
    workflowFailure: true,
    workflowStart: false,
    systemAlerts: true,
  },
};

interface AddNotificationChannelDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onAddChannel?: (channel: NewNotificationChannel) => void;
}

const AddNotificationChannelDialog: React.FC<
  AddNotificationChannelDialogProps
> = ({ open, onOpenChange, onAddChannel }) => {
  const [newChannel, setNewChannel] =
    useState<NewNotificationChannel>(defaultNewChannel);

  useEffect(() => {
    if (!open) {
      setNewChannel(defaultNewChannel);
    }
  }, [open]);

  const handleAddChannel = () => {
    if (onAddChannel && newChannel.name.trim()) {
      onAddChannel(newChannel);
      onOpenChange(false);
    }
  };

  const handleTypeChange = (value: NotificationChannelType) => {
    setNewChannel((prev) => ({
      ...prev,
      type: value,
      config: configDefaults[value],
    }));
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Add Notification Channel</DialogTitle>
          <DialogDescription>
            Create a new channel to receive notifications
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="channel-name" className="text-right">
              Name
            </Label>
            <Input
              id="channel-name"
              value={newChannel.name}
              onChange={(e) =>
                setNewChannel({ ...newChannel, name: e.target.value })
              }
              className="col-span-3"
              placeholder="Production Alerts"
            />
          </div>
          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="channel-type" className="text-right">
              Type
            </Label>
            <Select
              value={newChannel.type}
              onValueChange={(value: NotificationChannelType) =>
                handleTypeChange(value)
              }
            >
              <SelectTrigger className="col-span-3">
                <SelectValue placeholder="Select channel type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="email">Email</SelectItem>
                <SelectItem value="slack">Slack</SelectItem>
                <SelectItem value="webhook">Webhook</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {newChannel.type === "email" && (
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="recipients" className="text-right">
                Recipients
              </Label>
              <Input
                id="recipients"
                value={newChannel.config.recipients?.[0] || ""}
                onChange={(e) =>
                  setNewChannel({
                    ...newChannel,
                    config: {
                      ...newChannel.config,
                      recipients: [e.target.value],
                    },
                  })
                }
                className="col-span-3"
                placeholder="alerts@orcheo.dev"
              />
            </div>
          )}

          {newChannel.type === "slack" && (
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="slack-channel" className="text-right">
                Channel
              </Label>
              <Input
                id="slack-channel"
                value={newChannel.config.slackChannel || ""}
                onChange={(e) =>
                  setNewChannel({
                    ...newChannel,
                    config: {
                      ...newChannel.config,
                      slackChannel: e.target.value,
                    },
                  })
                }
                className="col-span-3"
                placeholder="#alerts"
              />
            </div>
          )}

          {newChannel.type === "webhook" && (
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="webhook-url" className="text-right">
                Webhook URL
              </Label>
              <Input
                id="webhook-url"
                value={newChannel.config.webhookUrl || ""}
                onChange={(e) =>
                  setNewChannel({
                    ...newChannel,
                    config: {
                      ...newChannel.config,
                      webhookUrl: e.target.value,
                    },
                  })
                }
                className="col-span-3"
                placeholder="https://example.com/webhook"
              />
            </div>
          )}

          <Separator className="my-2" />

          <div className="space-y-4">
            <h4 className="text-sm font-medium">Notification Events</h4>
            <NotificationEventToggles
              idPrefix="new-channel"
              events={newChannel.events}
              onToggle={(event, checked) =>
                setNewChannel({
                  ...newChannel,
                  events: {
                    ...newChannel.events,
                    [event]: checked,
                  },
                })
              }
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleAddChannel}>Add Channel</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default AddNotificationChannelDialog;
