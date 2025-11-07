import { useCallback, useMemo } from "react";

import { buildBackendHttpUrl } from "@/lib/config";
import type { UseChatKitOptions } from "@openai/chatkit-react";

import type { ChatInterfaceProps } from "./chat-interface.types";

type OptionalHandlers = Pick<
  ChatInterfaceProps,
  "onResponseStart" | "onResponseEnd" | "onThreadChange" | "onLog"
>;

type OptionParams = Pick<
  ChatInterfaceProps,
  | "chatkitOptions"
  | "getClientSecret"
  | "backendBaseUrl"
  | "sessionPayload"
  | "title"
  | "user"
  | "ai"
  | "initialMessages"
> &
  OptionalHandlers;

const useInitialGreeting = (
  initialMessages: ChatInterfaceProps["initialMessages"],
  aiId: string,
) =>
  useMemo(() => {
    const greeting = initialMessages?.find(
      (message) =>
        typeof message.content === "string" && message.sender?.id === aiId,
    );
    return greeting?.content as string | undefined;
  }, [aiId, initialMessages]);

const useSessionSecretResolver = ({
  getClientSecret,
  backendBaseUrl,
  sessionPayload,
  title,
  user,
  ai,
}: OptionParams) =>
  useCallback(
    async (currentSecret: string | null) => {
      if (getClientSecret) {
        return getClientSecret(currentSecret);
      }

      const url = buildBackendHttpUrl("/api/chatkit/session", backendBaseUrl);
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          current_client_secret: currentSecret,
          currentClientSecret: currentSecret,
          user,
          assistant: ai,
          metadata: { title, ...sessionPayload },
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to fetch ChatKit client secret");
      }

      const data = (await response.json()) as {
        client_secret?: string;
        clientSecret?: string;
      };

      const secret = data.client_secret ?? data.clientSecret;
      if (!secret) {
        throw new Error("ChatKit session response missing client secret");
      }

      return secret;
    },
    [ai, backendBaseUrl, getClientSecret, sessionPayload, title, user],
  );

const useHandlerComposer = () =>
  useCallback(
    <T extends unknown[]>(
      ...handlers: Array<((...args: T) => void) | undefined>
    ) => {
      const valid = handlers.filter(Boolean) as Array<(...args: T) => void>;
      if (valid.length === 0) {
        return undefined;
      }
      return (...args: T) => {
        valid.forEach((handler) => handler(...args));
      };
    },
    [],
  );

export const useChatInterfaceOptions = ({
  chatkitOptions,
  getClientSecret,
  backendBaseUrl,
  sessionPayload,
  title,
  user,
  ai,
  initialMessages,
  onResponseStart,
  onResponseEnd,
  onThreadChange,
  onLog,
}: OptionParams): UseChatKitOptions => {
  const resolveSessionSecret = useSessionSecretResolver({
    chatkitOptions,
    getClientSecret,
    backendBaseUrl,
    sessionPayload,
    title,
    user,
    ai,
    initialMessages,
    onResponseStart,
    onResponseEnd,
    onThreadChange,
    onLog,
  });
  const composeHandlers = useHandlerComposer();
  const initialGreeting = useInitialGreeting(initialMessages, ai.id);

  return useMemo(() => {
    const merged = {
      ...(chatkitOptions as UseChatKitOptions),
    } as UseChatKitOptions;

    merged.api = {
      ...(chatkitOptions?.api ?? {}),
      getClientSecret:
        chatkitOptions?.api?.getClientSecret ?? resolveSessionSecret,
    };

    if (!merged.header) {
      merged.header = {
        enabled: true,
        title: { enabled: true, text: title },
      };
    }

    if (!merged.startScreen && initialGreeting) {
      merged.startScreen = { greeting: initialGreeting };
    }

    merged.onResponseStart = composeHandlers(
      chatkitOptions?.onResponseStart,
      onResponseStart,
    );
    merged.onResponseEnd = composeHandlers(
      chatkitOptions?.onResponseEnd,
      onResponseEnd,
    );
    merged.onThreadChange = composeHandlers(
      chatkitOptions?.onThreadChange,
      onThreadChange,
    );
    merged.onThreadLoadStart = chatkitOptions?.onThreadLoadStart;
    merged.onThreadLoadEnd = chatkitOptions?.onThreadLoadEnd;
    merged.onLog = composeHandlers(chatkitOptions?.onLog, onLog);
    merged.onError = chatkitOptions?.onError;

    return merged;
  }, [
    chatkitOptions,
    composeHandlers,
    initialGreeting,
    onLog,
    onResponseEnd,
    onResponseStart,
    onThreadChange,
    resolveSessionSecret,
    title,
  ]);
};
