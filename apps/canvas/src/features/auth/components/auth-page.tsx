import { useState } from "react";
import { Link } from "react-router-dom";
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
import { GoogleLogo, GithubLogo } from "@features/auth/components/auth-logos";

interface AuthPageProps {
  type?: "login" | "signup";
}

export default function AuthPage({ type = "login" }: AuthPageProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    console.log("Form submitted", { email, password });
    // In a real app, this would handle authentication
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-cover bg-center bg-[url('https://picsum.photos/seed/orcheocanvas/1920/1080')] dark:bg-[url('https://picsum.photos/seed/orcheocanvasdark/1920/1080')]">
      <Card className="mx-auto min-w-80 max-w-md backdrop-blur-xl bg-primary/5 border-primary/25">
        <CardHeader className="space-y-1">
          <div className="flex items-center justify-center mb-2">
            <Link to="/" className="flex items-center gap-2 font-semibold">
              <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="h-4 w-4"
                >
                  <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
                </svg>
              </div>
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
            <Button variant="outline" className="w-full">
              <GoogleLogo className="h-5 w-5 mr-2" />
              Google
            </Button>
            <Button variant="outline" className="w-full">
              <GithubLogo className="h-5 w-5 mr-2" />
              GitHub
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
