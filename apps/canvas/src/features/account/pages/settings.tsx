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
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/design-system/ui/tabs";
import { Switch } from "@/design-system/ui/switch";
import { Label } from "@/design-system/ui/label";
import { Separator } from "@/design-system/ui/separator";
import TopNavigation from "@features/shared/components/top-navigation";
import ThemeSettings from "@features/account/components/theme-settings";
import useCredentialVault from "@/hooks/use-credential-vault";

export default function Settings() {
  const [emailNotifications, setEmailNotifications] = useState({
    workflow: true,
    security: true,
    marketing: false,
  });

  const [appSettings, setAppSettings] = useState({
    autoSave: true,
    showNodeLabels: true,
    confirmBeforeDelete: true,
    showMinimap: false,
  });

  const {
    credentials,
    isLoading: isCredentialsLoading,
    onAddCredential,
    onDeleteCredential,
  } = useCredentialVault();

  return (
    <div className="flex min-h-screen flex-col">
      <TopNavigation
        credentials={credentials}
        isCredentialsLoading={isCredentialsLoading}
        onAddCredential={onAddCredential}
        onDeleteCredential={onDeleteCredential}
      />

      <div className="flex-1 space-y-4 p-8 pt-6 mx-auto w-full max-w-7xl">
        <div className="flex items-center justify-between space-y-2">
          <h2 className="text-3xl font-bold tracking-tight">Settings</h2>
        </div>
        <Tabs defaultValue="appearance" className="space-y-4">
          <TabsList>
            <TabsTrigger value="appearance">Appearance</TabsTrigger>
            <TabsTrigger value="notifications">Notifications</TabsTrigger>
            <TabsTrigger value="application">Application</TabsTrigger>
            <TabsTrigger value="teams">Teams & Billing</TabsTrigger>
          </TabsList>
          <TabsContent value="appearance" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Theme & Accessibility</CardTitle>
                <CardDescription>
                  Customize the appearance of the application and accessibility
                  settings.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ThemeSettings />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Interface Density</CardTitle>
                <CardDescription>
                  Adjust the density of the user interface elements.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4">
                  <div className="grid grid-cols-3 gap-4">
                    <div className="flex flex-col items-center justify-between rounded-md border-2 border-muted bg-popover p-4 hover:bg-accent hover:text-accent-foreground">
                      <div className="mb-3 mt-2 space-y-2">
                        <div className="h-2 w-full rounded-lg bg-primary/10"></div>
                        <div className="h-2 w-full rounded-lg bg-primary/20"></div>
                        <div className="h-2 w-full rounded-lg bg-primary/10"></div>
                      </div>
                      <span className="text-xs font-medium">Compact</span>
                    </div>
                    <div className="flex flex-col items-center justify-between rounded-md border-2 border-primary bg-popover p-4 hover:bg-accent hover:text-accent-foreground">
                      <div className="mb-3 mt-2 space-y-3">
                        <div className="h-3 w-full rounded-lg bg-primary/10"></div>
                        <div className="h-3 w-full rounded-lg bg-primary/20"></div>
                        <div className="h-3 w-full rounded-lg bg-primary/10"></div>
                      </div>
                      <span className="text-xs font-medium">Default</span>
                    </div>
                    <div className="flex flex-col items-center justify-between rounded-md border-2 border-muted bg-popover p-4 hover:bg-accent hover:text-accent-foreground">
                      <div className="mb-3 mt-2 space-y-4">
                        <div className="h-4 w-full rounded-lg bg-primary/10"></div>
                        <div className="h-4 w-full rounded-lg bg-primary/20"></div>
                        <div className="h-4 w-full rounded-lg bg-primary/10"></div>
                      </div>
                      <span className="text-xs font-medium">Comfortable</span>
                    </div>
                  </div>
                </div>
              </CardContent>
              <CardFooter>
                <Button>Save Changes</Button>
              </CardFooter>
            </Card>
          </TabsContent>
          <TabsContent value="notifications" className="space-y-4">
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
                      setEmailNotifications({
                        ...emailNotifications,
                        workflow: checked,
                      })
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
                      setEmailNotifications({
                        ...emailNotifications,
                        security: checked,
                      })
                    }
                  />
                </div>
                <Separator />

                <div className="flex items-center justify-between space-x-2">
                  <Label
                    htmlFor="marketing"
                    className="flex flex-col space-y-1"
                  >
                    <span>Marketing</span>
                    <span className="font-normal text-xs text-muted-foreground">
                      Receive emails about new features and updates
                    </span>
                  </Label>
                  <Switch
                    id="marketing"
                    checked={emailNotifications.marketing}
                    onCheckedChange={(checked) =>
                      setEmailNotifications({
                        ...emailNotifications,
                        marketing: checked,
                      })
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
          </TabsContent>
          <TabsContent value="application" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Workflow Editor Settings</CardTitle>
                <CardDescription>
                  Configure how the workflow editor behaves.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between space-x-2">
                  <Label htmlFor="autosave" className="flex flex-col space-y-1">
                    <span>Auto-save Workflows</span>
                    <span className="font-normal text-xs text-muted-foreground">
                      Automatically save changes as you work
                    </span>
                  </Label>
                  <Switch
                    id="autosave"
                    checked={appSettings.autoSave}
                    onCheckedChange={(checked) =>
                      setAppSettings({ ...appSettings, autoSave: checked })
                    }
                  />
                </div>
                <Separator />

                <div className="flex items-center justify-between space-x-2">
                  <Label
                    htmlFor="nodelabels"
                    className="flex flex-col space-y-1"
                  >
                    <span>Show Node Labels</span>
                    <span className="font-normal text-xs text-muted-foreground">
                      Display labels on workflow nodes
                    </span>
                  </Label>
                  <Switch
                    id="nodelabels"
                    checked={appSettings.showNodeLabels}
                    onCheckedChange={(checked) =>
                      setAppSettings({
                        ...appSettings,
                        showNodeLabels: checked,
                      })
                    }
                  />
                </div>
                <Separator />

                <div className="flex items-center justify-between space-x-2">
                  <Label
                    htmlFor="confirmdelete"
                    className="flex flex-col space-y-1"
                  >
                    <span>Confirm Before Delete</span>
                    <span className="font-normal text-xs text-muted-foreground">
                      Show confirmation dialog before deleting nodes
                    </span>
                  </Label>
                  <Switch
                    id="confirmdelete"
                    checked={appSettings.confirmBeforeDelete}
                    onCheckedChange={(checked) =>
                      setAppSettings({
                        ...appSettings,
                        confirmBeforeDelete: checked,
                      })
                    }
                  />
                </div>
                <Separator />

                <div className="flex items-center justify-between space-x-2">
                  <Label htmlFor="minimap" className="flex flex-col space-y-1">
                    <span>Show Minimap</span>
                    <span className="font-normal text-xs text-muted-foreground">
                      Display minimap navigation in workflow editor
                    </span>
                  </Label>
                  <Switch
                    id="minimap"
                    checked={appSettings.showMinimap}
                    onCheckedChange={(checked) =>
                      setAppSettings({ ...appSettings, showMinimap: checked })
                    }
                  />
                </div>
              </CardContent>
              <CardFooter>
                <Button>Save Editor Settings</Button>
              </CardFooter>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Data Storage</CardTitle>
                <CardDescription>
                  Manage your data storage preferences.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-1">
                  <h3 className="font-medium">Storage Usage</h3>
                  <div className="h-4 w-full rounded-full bg-secondary">
                    <div
                      className="h-4 rounded-full bg-primary"
                      style={{ width: "35%" }}
                    ></div>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    3.5 GB used of 10 GB (35%)
                  </p>
                </div>
                <div className="pt-2">
                  <Button variant="outline">Manage Storage</Button>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
          <TabsContent value="teams" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Team Management</CardTitle>
                <CardDescription>
                  Manage your team members and their access levels.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="grid gap-2">
                    <h3 className="text-sm font-medium">Current Plan</h3>
                    <div className="flex items-center justify-between rounded-lg border p-4">
                      <div>
                        <p className="font-medium">Pro Plan</p>
                        <p className="text-sm text-muted-foreground">
                          $49/month • 10 team members • Unlimited workflows
                        </p>
                      </div>
                      <Button variant="outline">Upgrade</Button>
                    </div>
                  </div>
                  <div className="grid gap-2">
                    <h3 className="text-sm font-medium">Team Members</h3>
                    <div className="rounded-lg border">
                      <div className="flex items-center justify-between p-4">
                        <div className="flex items-center space-x-3">
                          <div className="h-9 w-9 rounded-full bg-primary/10"></div>
                          <div>
                            <p className="font-medium">Avery Chen</p>
                            <p className="text-sm text-muted-foreground">
                              avery@orcheo.dev • Owner
                            </p>
                          </div>
                        </div>
                        <Button variant="ghost" size="sm" disabled>
                          You
                        </Button>
                      </div>
                      <Separator />

                      <div className="flex items-center justify-between p-4">
                        <div className="flex items-center space-x-3">
                          <div className="h-9 w-9 rounded-full bg-primary/10"></div>
                          <div>
                            <p className="font-medium">Sky Patel</p>
                            <p className="text-sm text-muted-foreground">
                              sky@orcheo.dev • Admin
                            </p>
                          </div>
                        </div>
                        <Button variant="ghost" size="sm">
                          Manage
                        </Button>
                      </div>
                      <Separator />

                      <div className="flex items-center justify-between p-4">
                        <div className="flex items-center space-x-3">
                          <div className="h-9 w-9 rounded-full bg-primary/10"></div>
                          <div>
                            <p className="font-medium">Riley Morgan</p>
                            <p className="text-sm text-muted-foreground">
                              riley@orcheo.dev • Editor
                            </p>
                          </div>
                        </div>
                        <Button variant="ghost" size="sm">
                          Manage
                        </Button>
                      </div>
                    </div>
                  </div>
                  <div className="flex justify-between">
                    <Button variant="outline">Invite Team Member</Button>
                    <Button variant="outline">Manage Team</Button>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Billing</CardTitle>
                <CardDescription>
                  Manage your billing information and view your invoices.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="rounded-lg border">
                  <div className="flex items-center justify-between p-4">
                    <div>
                      <p className="font-medium">Payment Method</p>
                      <p className="text-sm text-muted-foreground">
                        Visa ending in 4242
                      </p>
                    </div>
                    <Button variant="ghost" size="sm">
                      Change
                    </Button>
                  </div>
                  <Separator />

                  <div className="flex items-center justify-between p-4">
                    <div>
                      <p className="font-medium">Billing Cycle</p>
                      <p className="text-sm text-muted-foreground">
                        Monthly • Next billing date: Nov 15, 2023
                      </p>
                    </div>
                    <Button variant="ghost" size="sm">
                      Change
                    </Button>
                  </div>
                </div>
                <div className="grid gap-2">
                  <h3 className="text-sm font-medium">Recent Invoices</h3>
                  <div className="rounded-lg border">
                    <div className="flex items-center justify-between p-4">
                      <div>
                        <p className="font-medium">October 2023</p>
                        <p className="text-sm text-muted-foreground">
                          Pro Plan • $49.00
                        </p>
                      </div>
                      <Button variant="ghost" size="sm">
                        Download
                      </Button>
                    </div>
                    <Separator />

                    <div className="flex items-center justify-between p-4">
                      <div>
                        <p className="font-medium">September 2023</p>
                        <p className="text-sm text-muted-foreground">
                          Pro Plan • $49.00
                        </p>
                      </div>
                      <Button variant="ghost" size="sm">
                        Download
                      </Button>
                    </div>
                  </div>
                </div>
              </CardContent>
              <CardFooter>
                <Button variant="outline">View All Invoices</Button>
              </CardFooter>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
