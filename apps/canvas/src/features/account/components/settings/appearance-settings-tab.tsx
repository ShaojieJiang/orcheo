import { Button } from "@/design-system/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/design-system/ui/card";
import ThemeSettings from "@features/account/components/theme-settings";

const AppearanceSettingsTab = () => (
  <div className="space-y-4">
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
  </div>
);

export default AppearanceSettingsTab;
