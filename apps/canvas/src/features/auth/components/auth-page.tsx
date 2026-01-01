import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Button } from "@/design-system/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/design-system/ui/card";
import { Loader2 } from "lucide-react";
import { GoogleLogo, GithubLogo } from "@features/auth/components/auth-logos";
import { toast } from "@/hooks/use-toast";
import { startOidcLogin } from "@features/auth/lib/oidc-client";

export default function AuthPage() {
  const location = useLocation();
  const [providerLoading, setProviderLoading] = useState<
    "google" | "github" | null
  >(null);
  const redirectTo = (location.state as { from?: string } | null)?.from ?? "/";

  const startProviderLogin = async (provider: "google" | "github") => {
    setProviderLoading(provider);
    try {
      await startOidcLogin({ provider, redirectTo });
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Unable to start the login flow.";
      toast({
        title: "Login failed",
        description: message,
        variant: "destructive",
      });
    } finally {
      setProviderLoading(null);
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-slate-950 text-foreground dark:bg-slate-950">
      <div
        className="absolute inset-0 bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 dark:from-slate-950 dark:via-slate-900/80 dark:to-black"
        aria-hidden="true"
      />
      <div
        className="absolute inset-0 opacity-60 mix-blend-soft-light"
        style={{
          backgroundImage:
            "radial-gradient(circle at 20% 20%, rgba(148, 163, 184, 0.12), transparent 45%), radial-gradient(circle at 80% 30%, rgba(56, 189, 248, 0.15), transparent 50%), radial-gradient(circle at 50% 80%, rgba(45, 212, 191, 0.12), transparent 55%)",
        }}
        aria-hidden="true"
      />
      <Card className="relative z-10 mx-auto min-w-80 max-w-md border-primary/25 bg-primary/5 backdrop-blur-xl">
        <CardHeader className="space-y-1">
          <div className="flex items-center justify-center mb-2">
            <Link to="/" className="flex items-center gap-2 font-semibold">
              <img src="/favicon.ico" alt="Orcheo Logo" className="h-8 w-8" />
              <span className="text-xl font-bold">Orcheo Canvas</span>
            </Link>
          </div>
          <CardTitle className="text-2xl">Sign in</CardTitle>
          <CardDescription>Continue with your OAuth provider.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          <div className="grid grid-cols-2 gap-2">
            <Button
              variant="outline"
              className="w-full"
              onClick={() => startProviderLogin("google")}
              disabled={providerLoading !== null}
            >
              {providerLoading === "google" ? (
                <Loader2 className="h-5 w-5 mr-2 animate-spin" />
              ) : (
                <GoogleLogo className="h-5 w-5 mr-2" />
              )}
              {providerLoading === "google" ? "Signing in…" : "Google"}
            </Button>
            <Button
              variant="outline"
              className="w-full"
              onClick={() => startProviderLogin("github")}
              disabled={providerLoading !== null}
            >
              {providerLoading === "github" ? (
                <Loader2 className="h-5 w-5 mr-2 animate-spin" />
              ) : (
                <GithubLogo className="h-5 w-5 mr-2" />
              )}
              {providerLoading === "github" ? "Signing in…" : "GitHub"}
            </Button>
          </div>
          <div className="mt-4 text-center text-sm text-muted-foreground">
            Need access? Contact your admin.
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
