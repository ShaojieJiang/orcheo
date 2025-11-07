export type NotificationChannelType = "email" | "slack" | "webhook";

export interface NotificationChannelConfig {
  recipients?: string[];
  webhookUrl?: string;
  slackChannel?: string;
}

export interface NotificationChannelEvents {
  workflowSuccess: boolean;
  workflowFailure: boolean;
  workflowStart: boolean;
  systemAlerts: boolean;
}

export interface NotificationChannel {
  id: string;
  type: NotificationChannelType;
  name: string;
  enabled: boolean;
  config: NotificationChannelConfig;
  events: NotificationChannelEvents;
}

export type NewNotificationChannel = Omit<NotificationChannel, "id">;
export type NotificationEventKey = keyof NotificationChannelEvents;

export interface NotificationSettingsProps {
  channels?: NotificationChannel[];
  onAddChannel?: (channel: NewNotificationChannel) => void;
  onUpdateChannel?: (id: string, channel: Partial<NotificationChannel>) => void;
  onDeleteChannel?: (id: string) => void;
  className?: string;
}
