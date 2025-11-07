import { useMemo, useState } from "react";
import TopNavigation from "@features/shared/components/top-navigation";
import useCredentialVault from "@/hooks/use-credential-vault";
import { SupportHeader } from "@features/support/components/support-header";
import { SupportResources } from "@features/support/components/support-resources";
import { SupportHelpTabs } from "@features/support/components/support-help-tabs";
import { SupportChatCallout } from "@features/support/components/support-chat-callout";
import type { ChatMessageProps } from "@features/shared/components/chat-message";

const user = {
  id: "user-1",
  name: "Avery Chen",
  avatar: "https://avatar.vercel.sh/avery",
};

const ai = {
  id: "ai-1",
  name: "Orcheo Canvas Support",
  avatar: "https://avatar.vercel.sh/orcheo-canvas",
  isAI: true,
};

export default function HelpSupport() {
  const [searchQuery, setSearchQuery] = useState("");
  const initialMessages = useMemo<ChatMessageProps[]>(
    () => [
      {
        id: "msg-1",
        content:
          "Hello! I'm the Orcheo Canvas support assistant. How can I help you today?",
        sender: ai,
        timestamp: new Date(Date.now() - 60000),
      },
    ],
    [],
  );

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

      <main className="mx-auto w-full max-w-7xl flex-1 space-y-6 p-8 pt-6">
        <SupportHeader
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
        />

        <SupportResources />

        <SupportHelpTabs />

        <SupportChatCallout
          ai={ai}
          user={user}
          initialMessages={initialMessages}
        />
      </main>
    </div>
  );
}
