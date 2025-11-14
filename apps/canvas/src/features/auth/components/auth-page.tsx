import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/design-system/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/design-system/ui/card";
import { Input } from "@/design-system/ui/input";
import { Label } from "@/design-system/ui/label";
import { Separator } from "@/design-system/ui/separator";
import { Loader2 } from "lucide-react";
import { GoogleLogo, GithubLogo } from "@features/auth/components/auth-logos";
import { toast } from "@/hooks/use-toast";
import { buildBackendHttpUrl } from "@/lib/config";

interface AuthPageProps {
  type?: "login" | "signup";
}

export default function AuthPage({ type = "login" }: AuthPageProps) {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [providerLoading, setProviderLoading] = useState<
    "google" | "github" | null
  >(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    toast({
      title: "Authentication coming soon",
      description:
        "The canvas prototype does not include authentication yet. Your credentials were not sent anywhere.",
    });

    // In a real app, this would handle authentication
  };

  const startDevLogin = async (provider: "google" | "github") => {
    setProviderLoading(provider);
    try {
      const response = await fetch(buildBackendHttpUrl("/api/auth/dev/login"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify({
          provider,
          email: email || undefined,
          name: email ? email.split("@")[0] : undefined,
        }),
      });

      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        const message =
          detail?.message ||
          detail?.detail?.message ||
          "Developer login is disabled for this environment. Set ORCHEO_AUTH_DEV_LOGIN_ENABLED=true on the backend.";
        throw new Error(message);
      }

      toast({
        title: "Signed in",
        description: `Authenticated via ${provider} (dev mode).`,
      });
      navigate("/");
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
              <img src="/favicon.png" alt="Orcheo Logo" className="h-8 w-8" />
              <span className="text-xl font-bold">Orcheo Canvas</span>
            </Link>
          </div>
          <CardTitle className="text-2xl">
            {type === "login" ? "Login" : "Create an account"}
          </CardTitle>
          <CardDescription>
            {type === "login"
              ? "Enter your email below to login to your account"
              : "Enter your information below to create your account"}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          <div className="grid grid-cols-2 gap-2">
            <Button
              variant="outline"
              className="w-full"
              onClick={() => startDevLogin("google")}
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
              onClick={() => startDevLogin("github")}
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

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <Separator className="w-full" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-background px-2 text-muted-foreground">
                Or continue with
              </span>
            </div>
          </div>

          <form onSubmit={handleSubmit}>
            <div className="grid gap-4">
              <div className="grid gap-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="you@orcheo.dev"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>
              <div className="grid gap-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="password">Password</Label>
                  {type === "login" && (
                    <Link
                      to="/forgot-password"
                      className="text-sm text-primary underline-offset-4 hover:underline"
                    >
                      Forgot password?
                    </Link>
                  )}
                </div>
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </div>
              <Button className="w-full" type="submit">
                {type === "login" ? "Login" : "Create account"}
              </Button>
            </div>
          </form>

          <div className="mt-4 text-center text-sm">
            {type === "login" ? (
              <div>
                Don&apos;t have an account?{" "}
                <Link
                  to="/signup"
                  className="text-primary underline-offset-4 hover:underline"
                >
                  Sign up
                </Link>
              </div>
            ) : (
              <div>
                Already have an account?{" "}
                <Link
                  to="/login"
                  className="text-primary underline-offset-4 hover:underline"
                >
                  Login
                </Link>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
