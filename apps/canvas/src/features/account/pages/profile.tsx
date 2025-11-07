import { useState } from "react";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/design-system/ui/tabs";
import TopNavigation from "@features/shared/components/top-navigation";
import useCredentialVault from "@/hooks/use-credential-vault";
import type { ProfileUser } from "./profile/types";
import { ProfileGeneralTab } from "./profile/components/profile-general-tab";
import { ProfileSecurityTab } from "./profile/components/profile-security-tab";
import { ProfileApiKeysTab } from "./profile/components/profile-api-keys-tab";

export default function Profile() {
  const [user] = useState<ProfileUser>({
    name: "Avery Chen",
    email: "avery@orcheo.dev",
    avatar: "https://avatar.vercel.sh/avery",
    role: "Admin",
    joinDate: "January 2023",
    twoFactorEnabled: false,
  });

  const {
    credentials,
    isLoading: isCredentialsLoading,
    onAddCredential,
    onDeleteCredential,
  } = useCredentialVault({ actorName: user.name });

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
          <h2 className="text-3xl font-bold tracking-tight">Profile</h2>
        </div>
        <Tabs defaultValue="general" className="space-y-4">
          <TabsList>
            <TabsTrigger value="general">General</TabsTrigger>
            <TabsTrigger value="security">Security</TabsTrigger>
            <TabsTrigger value="api-keys">API Keys</TabsTrigger>
          </TabsList>
          <TabsContent value="general" className="space-y-4">
            <ProfileGeneralTab user={user} />
          </TabsContent>
          <TabsContent value="security" className="space-y-4">
            <ProfileSecurityTab user={user} />
          </TabsContent>
          <TabsContent value="api-keys" className="space-y-4">
            <ProfileApiKeysTab />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
