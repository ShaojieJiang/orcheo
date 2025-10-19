import React, { useState } from "react";
import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";
import { Label } from "@/design-system/ui/label";
import { Switch } from "@/design-system/ui/switch";
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
  DialogTrigger,
} from "@/design-system/ui/dialog";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/design-system/ui/card";
import {
  Bell,
  Mail,
  MessageSquare,
  Webhook,
  Plus,
  Trash,
  AlertCircle,
  CheckCircle,
  Clock,
  Settings,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface NotificationChannel {
  id: string;
  type: "email" | "slack" | "webhook";
  name: string;
  enabled: boolean;
  config: {
    recipients?: string[];
    webhookUrl?: string;
    slackChannel?: string;
  };
  events: {
    workflowSuccess: boolean;
    workflowFailure: boolean;
    workflowStart: boolean;
    systemAlerts: boolean;
  };
}

interface NotificationSettingsProps {
  channels?: NotificationChannel[];
  onAddChannel?: (channel: Omit<NotificationChannel, "id">) => void;
  onUpdateChannel?: (id: string, channel: Partial<NotificationChannel>) => void;
  onDeleteChannel?: (id: string) => void;
  className?: string;
}

export default function NotificationSettings({
  channels = [],
  onAddChannel,
  onUpdateChannel,
  onDeleteChannel,
  className,
}: NotificationSettingsProps) {
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [newChannel, setNewChannel] = useState<Omit<NotificationChannel, "id">>(
    {
      type: "email",
      name: "",
      enabled: true,
      config: {
        recipients: [""],
      },
      events: {
        workflowSuccess: false,
        workflowFailure: true,
        workflowStart: false,
        systemAlerts: true,
      },
    },
  );

  const handleAddChannel = () => {
    if (onAddChannel && newChannel.name.trim()) {
      onAddChannel(newChannel);
      setNewChannel({
        type: "email",
        name: "",
        enabled: true,
        config: {
          recipients: [""],
        },
        events: {
          workflowSuccess: false,
          workflowFailure: true,
          workflowStart: false,
          systemAlerts: true,
        },
      });
      setIsAddDialogOpen(false);
    }
  };

  const handleToggleEvent = (
    channelId: string,
    event: keyof NotificationChannel["events"],
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
    if (onUpdateChannel) {
      onUpdateChannel(channelId, { enabled });
    }
  };

  const getChannelIcon = (type: string) => {
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
        <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="h-4 w-4 mr-2" />
              Add Channel
            </Button>
          </DialogTrigger>
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
                  onValueChange={(value: "email" | "slack" | "webhook") => {
                    let config = {};
                    switch (value) {
                      case "email":
                        config = { recipients: [""] };
                        break;
                      case "slack":
                        config = { slackChannel: "#alerts" };
                        break;
                      case "webhook":
                        config = { webhookUrl: "" };
                        break;
                    }
                    setNewChannel({
                      ...newChannel,
                      type: value,
                      config,
                    });
                  }}
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
                <div className="grid grid-cols-1 gap-3">
                  <div className="flex items-center justify-between">
                    <Label
                      htmlFor="workflow-success"
                      className="flex items-center gap-2"
                    >
                      <CheckCircle className="h-4 w-4 text-green-500" />
                      Workflow Success
                    </Label>
                    <Switch
                      id="workflow-success"
                      checked={newChannel.events.workflowSuccess}
                      onCheckedChange={(checked) =>
                        setNewChannel({
                          ...newChannel,
                          events: {
                            ...newChannel.events,
                            workflowSuccess: checked,
                          },
                        })
                      }
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <Label
                      htmlFor="workflow-failure"
                      className="flex items-center gap-2"
                    >
                      <AlertCircle className="h-4 w-4 text-red-500" />
                      Workflow Failure
                    </Label>
                    <Switch
                      id="workflow-failure"
                      checked={newChannel.events.workflowFailure}
                      onCheckedChange={(checked) =>
                        setNewChannel({
                          ...newChannel,
                          events: {
                            ...newChannel.events,
                            workflowFailure: checked,
                          },
                        })
                      }
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <Label
                      htmlFor="workflow-start"
                      className="flex items-center gap-2"
                    >
                      <Clock className="h-4 w-4 text-blue-500" />
                      Workflow Start
                    </Label>
                    <Switch
                      id="workflow-start"
                      checked={newChannel.events.workflowStart}
                      onCheckedChange={(checked) =>
                        setNewChannel({
                          ...newChannel,
                          events: {
                            ...newChannel.events,
                            workflowStart: checked,
                          },
                        })
                      }
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <Label
                      htmlFor="system-alerts"
                      className="flex items-center gap-2"
                    >
                      <Settings className="h-4 w-4 text-amber-500" />
                      System Alerts
                    </Label>
                    <Switch
                      id="system-alerts"
                      checked={newChannel.events.systemAlerts}
                      onCheckedChange={(checked) =>
                        setNewChannel({
                          ...newChannel,
                          events: {
                            ...newChannel.events,
                            systemAlerts: checked,
                          },
                        })
                      }
                    />
                  </div>
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setIsAddDialogOpen(false)}
              >
                Cancel
              </Button>
              <Button onClick={handleAddChannel}>Add Channel</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <Separator />

      {channels.length === 0 ? (
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
      ) : (
        <div className="grid gap-6 md:grid-cols-2">
          {channels.map((channel) => (
            <Card
              key={channel.id}
              className={!channel.enabled ? "opacity-60" : ""}
            >
              <CardHeader className="pb-2">
                <div className="flex justify-between items-start">
                  <div className="flex items-center gap-2">
                    {getChannelIcon(channel.type)}
                    <CardTitle className="text-lg">{channel.name}</CardTitle>
                  </div>
                  <Switch
                    checked={channel.enabled}
                    onCheckedChange={(checked) =>
                      handleToggleEnabled(channel.id, checked)
                    }
                  />
                </div>
                <CardDescription>
                  {channel.type === "email" && (
                    <span>
                      Email to {channel.config.recipients?.join(", ")}
                    </span>
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
                <div className="grid grid-cols-1 gap-3">
                  <div className="flex items-center justify-between">
                    <Label
                      htmlFor={`${channel.id}-workflow-success`}
                      className="flex items-center gap-2 text-sm"
                    >
                      <CheckCircle className="h-3 w-3 text-green-500" />
                      Workflow Success
                    </Label>
                    <Switch
                      id={`${channel.id}-workflow-success`}
                      checked={channel.events.workflowSuccess}
                      onCheckedChange={(checked) =>
                        handleToggleEvent(
                          channel.id,
                          "workflowSuccess",
                          checked,
                        )
                      }
                      disabled={!channel.enabled}
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <Label
                      htmlFor={`${channel.id}-workflow-failure`}
                      className="flex items-center gap-2 text-sm"
                    >
                      <AlertCircle className="h-3 w-3 text-red-500" />
                      Workflow Failure
                    </Label>
                    <Switch
                      id={`${channel.id}-workflow-failure`}
                      checked={channel.events.workflowFailure}
                      onCheckedChange={(checked) =>
                        handleToggleEvent(
                          channel.id,
                          "workflowFailure",
                          checked,
                        )
                      }
                      disabled={!channel.enabled}
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <Label
                      htmlFor={`${channel.id}-workflow-start`}
                      className="flex items-center gap-2 text-sm"
                    >
                      <Clock className="h-3 w-3 text-blue-500" />
                      Workflow Start
                    </Label>
                    <Switch
                      id={`${channel.id}-workflow-start`}
                      checked={channel.events.workflowStart}
                      onCheckedChange={(checked) =>
                        handleToggleEvent(channel.id, "workflowStart", checked)
                      }
                      disabled={!channel.enabled}
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <Label
                      htmlFor={`${channel.id}-system-alerts`}
                      className="flex items-center gap-2 text-sm"
                    >
                      <Settings className="h-3 w-3 text-amber-500" />
                      System Alerts
                    </Label>
                    <Switch
                      id={`${channel.id}-system-alerts`}
                      checked={channel.events.systemAlerts}
                      onCheckedChange={(checked) =>
                        handleToggleEvent(channel.id, "systemAlerts", checked)
                      }
                      disabled={!channel.enabled}
                    />
                  </div>
                </div>
              </CardContent>
              <CardFooter className="pt-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="text-destructive hover:text-destructive"
                  onClick={() => onDeleteChannel && onDeleteChannel(channel.id)}
                >
                  <Trash className="h-3 w-3 mr-1" />
                  Remove
                </Button>
              </CardFooter>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
