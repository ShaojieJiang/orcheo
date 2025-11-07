import { useState } from "react";
import { Button } from "@/design-system/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/design-system/ui/card";
import { Label } from "@/design-system/ui/label";
import { Separator } from "@/design-system/ui/separator";
import { Switch } from "@/design-system/ui/switch";

type EmailNotificationState = {
  workflow: boolean;
  security: boolean;
  marketing: boolean;
};

const NotificationSettingsTab = () => {
  const [emailNotifications, setEmailNotifications] =
    useState<EmailNotificationState>({
      workflow: true,
      security: true,
      marketing: false,
    });

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Email Notifications</CardTitle>
          <CardDescription>
            Configure when you'll receive email notifications.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between space-x-2">
            <Label htmlFor="workflow" className="flex flex-col space-y-1">
              <span>Workflow Notifications</span>
              <span className="font-normal text-xs text-muted-foreground">
                Receive emails when workflows fail or complete
              </span>
            </Label>
            <Switch
              id="workflow"
              checked={emailNotifications.workflow}
              onCheckedChange={(checked) =>
                setEmailNotifications((prev) => ({
                  ...prev,
                  workflow: checked,
                }))
              }
            />
          </div>
          <Separator />

          <div className="flex items-center justify-between space-x-2">
            <Label htmlFor="security" className="flex flex-col space-y-1">
              <span>Security Alerts</span>
              <span className="font-normal text-xs text-muted-foreground">
                Receive emails about security events
              </span>
            </Label>
            <Switch
              id="security"
              checked={emailNotifications.security}
              onCheckedChange={(checked) =>
                setEmailNotifications((prev) => ({
                  ...prev,
                  security: checked,
                }))
              }
            />
          </div>
          <Separator />

          <div className="flex items-center justify-between space-x-2">
            <Label htmlFor="marketing" className="flex flex-col space-y-1">
              <span>Marketing</span>
              <span className="font-normal text-xs text-muted-foreground">
                Receive emails about new features and updates
              </span>
            </Label>
            <Switch
              id="marketing"
              checked={emailNotifications.marketing}
              onCheckedChange={(checked) =>
                setEmailNotifications((prev) => ({
                  ...prev,
                  marketing: checked,
                }))
              }
            />
          </div>
        </CardContent>
        <CardFooter>
          <Button>Save Notification Settings</Button>
        </CardFooter>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>In-App Notifications</CardTitle>
          <CardDescription>
            Configure notifications that appear within the application.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4">
            <div className="flex items-center space-x-4 rounded-md border p-4">
              <div>
                <p className="text-sm font-medium leading-none">
                  Workflow Status Updates
                </p>
                <p className="text-sm text-muted-foreground">
                  Show notifications when workflow status changes
                </p>
              </div>
              <div className="ml-auto">
                <Switch defaultChecked />
              </div>
            </div>
            <div className="flex items-center space-x-4 rounded-md border p-4">
              <div>
                <p className="text-sm font-medium leading-none">
                  Team Mentions
                </p>
                <p className="text-sm text-muted-foreground">
                  Show notifications when you're mentioned in comments
                </p>
              </div>
              <div className="ml-auto">
                <Switch defaultChecked />
              </div>
            </div>
            <div className="flex items-center space-x-4 rounded-md border p-4">
              <div>
                <p className="text-sm font-medium leading-none">
                  System Announcements
                </p>
                <p className="text-sm text-muted-foreground">
                  Show notifications about system updates
                </p>
              </div>
              <div className="ml-auto">
                <Switch />
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default NotificationSettingsTab;
