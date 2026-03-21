import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/design-system/ui/badge";
import { Button } from "@/design-system/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/design-system/ui/card";
import { Separator } from "@/design-system/ui/separator";

const CONTEXT_URL = "http://localhost:3333/context/sessions";

function useCopied() {
  const [copied, setCopied] = useState(false);
  const copy = useCallback((text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, []);
  return { copied, copy };
}

const AgentSettingsTab = () => {
  const [sessionCount, setSessionCount] = useState<number | null>(null);
  const [serverRunning, setServerRunning] = useState(false);
  const { copied: copiedLogin, copy: copyLogin } = useCopied();
  const { copied: copiedStart, copy: copyStart } = useCopied();

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const res = await fetch(CONTEXT_URL);
        if (!cancelled) {
          const sessions = await res.json();
          setSessionCount(Array.isArray(sessions) ? sessions.length : 0);
          setServerRunning(true);
        }
      } catch {
        if (!cancelled) {
          setSessionCount(null);
          setServerRunning(false);
        }
      }
    };
    poll();
    const interval = setInterval(poll, 10_000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Connect your agent</CardTitle>
          <CardDescription>
            Use Claude Code, Cursor, or any CLI-capable coding agent to read and
            modify your Orcheo workflows directly from the terminal.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-3">
            <h3 className="text-sm font-medium">Quick start</h3>
            <ol className="list-decimal list-inside space-y-2 text-sm text-muted-foreground">
              <li>
                Authenticate the CLI:
                <div className="mt-1 flex items-center gap-2">
                  <code className="rounded bg-muted px-2 py-1 text-xs">
                    orcheo auth login
                  </code>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 px-2 text-xs"
                    onClick={() => copyLogin("orcheo auth login")}
                  >
                    {copiedLogin ? "Copied!" : "Copy"}
                  </Button>
                </div>
              </li>
              <li>
                Start the browser context bridge:
                <div className="mt-1 flex items-center gap-2">
                  <code className="rounded bg-muted px-2 py-1 text-xs">
                    orcheo browser-aware
                  </code>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 px-2 text-xs"
                    onClick={() => copyStart("orcheo browser-aware")}
                  >
                    {copiedStart ? "Copied!" : "Copy"}
                  </Button>
                </div>
              </li>
              <li>
                Open a workflow in Canvas — your agent will automatically know
                what you&apos;re looking at.
              </li>
            </ol>
          </div>

          <Separator />

          <div className="space-y-2">
            <h3 className="text-sm font-medium">Connection status</h3>
            <div className="flex items-center gap-2">
              <Badge variant={serverRunning ? "default" : "secondary"}>
                {serverRunning ? "Connected" : "Not connected"}
              </Badge>
              {serverRunning && sessionCount !== null && (
                <span className="text-sm text-muted-foreground">
                  {sessionCount} active{" "}
                  {sessionCount === 1 ? "session" : "sessions"}
                </span>
              )}
            </div>
            {!serverRunning && (
              <p className="text-xs text-muted-foreground">
                Run{" "}
                <code className="rounded bg-muted px-1 py-0.5">
                  orcheo browser-aware
                </code>{" "}
                in your terminal to connect.
              </p>
            )}
          </div>

          <Separator />

          <div className="space-y-2">
            <h3 className="text-sm font-medium">Agent commands</h3>
            <div className="space-y-1 text-sm text-muted-foreground">
              <p>
                <code className="rounded bg-muted px-1 py-0.5">
                  orcheo context
                </code>{" "}
                — See what workflow you have open
              </p>
              <p>
                <code className="rounded bg-muted px-1 py-0.5">
                  orcheo workflow show &lt;id&gt;
                </code>{" "}
                — View workflow details
              </p>
              <p>
                <code className="rounded bg-muted px-1 py-0.5">
                  orcheo workflow download &lt;id&gt;
                </code>{" "}
                — Download workflow script
              </p>
              <p>
                <code className="rounded bg-muted px-1 py-0.5">
                  orcheo workflow upload --id &lt;id&gt; &lt;file&gt;
                </code>{" "}
                — Upload updated script
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default AgentSettingsTab;
