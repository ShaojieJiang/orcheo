import { Badge } from "@/design-system/ui/badge";
import { Button } from "@/design-system/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/design-system/ui/card";
import { Input } from "@/design-system/ui/input";
import type { ProfileUser } from "../types";

interface ProfileSecurityTabProps {
  user: ProfileUser;
}

export function ProfileSecurityTab({ user }: ProfileSecurityTabProps) {
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Password</CardTitle>
          <CardDescription>
            Change your password here. After saving, you'll be logged out.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="current">
              Current Password
            </label>
            <Input id="current" type="password" />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="new">
              New Password
            </label>
            <Input id="new" type="password" />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="confirm">
              Confirm Password
            </label>
            <Input id="confirm" type="password" />
          </div>
        </CardContent>
        <CardFooter>
          <Button>Change Password</Button>
        </CardFooter>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Two-Factor Authentication</CardTitle>
          <CardDescription>
            Add an extra layer of security to your account.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between rounded-lg border p-4">
            <div className="space-y-0.5">
              <div className="font-medium">Two-Factor Authentication (2FA)</div>
              <div className="text-sm text-muted-foreground">
                {user.twoFactorEnabled
                  ? "Two-factor authentication is enabled."
                  : "Two-factor authentication is not enabled yet."}
              </div>
            </div>
            <Button variant={user.twoFactorEnabled ? "destructive" : "default"}>
              {user.twoFactorEnabled ? "Disable" : "Enable"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Active Sessions</CardTitle>
          <CardDescription>
            Manage your active sessions across devices.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex items-center justify-between rounded-lg border p-4">
              <div className="space-y-0.5">
                <div className="font-medium">Current Session</div>
                <div className="text-sm text-muted-foreground">
                  Chrome on macOS • San Francisco, CA • Active now
                </div>
              </div>
              <Badge>Current</Badge>
            </div>
            <div className="flex items-center justify-between rounded-lg border p-4">
              <div className="space-y-0.5">
                <div className="font-medium">Mobile App</div>
                <div className="text-sm text-muted-foreground">
                  iOS • New York, NY • Active 2 days ago
                </div>
              </div>
              <Button variant="outline" size="sm">
                Revoke
              </Button>
            </div>
          </div>
        </CardContent>
        <CardFooter>
          <Button variant="destructive">Sign Out All Devices</Button>
        </CardFooter>
      </Card>
    </div>
  );
}
