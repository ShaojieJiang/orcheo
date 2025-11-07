import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/design-system/ui/tabs";
import useCredentialVault from "@/hooks/use-credential-vault";
import AppearanceSettingsTab from "@features/account/components/settings/appearance-settings-tab";
import ApplicationSettingsTab from "@features/account/components/settings/application-settings-tab";
import NotificationSettingsTab from "@features/account/components/settings/notification-settings-tab";
import TeamBillingSettingsTab from "@features/account/components/settings/team-billing-settings-tab";
import TopNavigation from "@features/shared/components/top-navigation";

export default function Settings() {
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
            <AppearanceSettingsTab />
          </TabsContent>
          <TabsContent value="notifications" className="space-y-4">
            <NotificationSettingsTab />
          </TabsContent>
          <TabsContent value="application" className="space-y-4">
            <ApplicationSettingsTab />
          </TabsContent>
          <TabsContent value="teams" className="space-y-4">
            <TeamBillingSettingsTab />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
