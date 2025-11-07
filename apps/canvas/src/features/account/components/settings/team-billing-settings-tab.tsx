import { Button } from "@/design-system/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/design-system/ui/card";
import { Separator } from "@/design-system/ui/separator";

const TeamBillingSettingsTab = () => (
  <div className="space-y-4">
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
  </div>
);

export default TeamBillingSettingsTab;
