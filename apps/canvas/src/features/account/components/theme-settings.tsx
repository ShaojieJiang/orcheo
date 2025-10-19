import React, { useState, useEffect } from "react";
import { Button } from "@/design-system/ui/button";
import { Label } from "@/design-system/ui/label";
import { Switch } from "@/design-system/ui/switch";
import { RadioGroup, RadioGroupItem } from "@/design-system/ui/radio-group";
import { Separator } from "@/design-system/ui/separator";
import { Sun, Moon, Monitor, Palette, Sliders, Zap, Check } from "lucide-react";
import { cn } from "@/lib/utils";

interface ThemeSettingsProps {
  onThemeChange?: (theme: "light" | "dark" | "system") => void;
  onReducedMotionChange?: (enabled: boolean) => void;
  onHighContrastChange?: (enabled: boolean) => void;
  className?: string;
}

export default function ThemeSettings({
  onThemeChange,
  onReducedMotionChange,
  onHighContrastChange,
  className,
}: ThemeSettingsProps) {
  const [theme, setTheme] = useState<"light" | "dark" | "system">("system");
  const [reducedMotion, setReducedMotion] = useState(false);
  const [highContrast, setHighContrast] = useState(false);
  const [accentColor, setAccentColor] = useState("blue");

  // Initialize theme from localStorage or system preference
  useEffect(() => {
    const savedTheme = localStorage.getItem("theme") as
      | "light"
      | "dark"
      | "system"
      | null;
    if (savedTheme) {
      setTheme(savedTheme);
    } else {
      const systemTheme = window.matchMedia("(prefers-color-scheme: dark)")
        .matches
        ? "dark"
        : "light";
      setTheme("system");
      document.documentElement.classList.toggle("dark", systemTheme === "dark");
    }

    const savedReducedMotion = localStorage.getItem("reducedMotion") === "true";
    setReducedMotion(savedReducedMotion);

    const savedHighContrast = localStorage.getItem("highContrast") === "true";
    setHighContrast(savedHighContrast);

    const savedAccentColor = localStorage.getItem("accentColor") || "blue";
    setAccentColor(savedAccentColor);
  }, []);

  // Apply theme changes
  useEffect(() => {
    localStorage.setItem("theme", theme);

    if (theme === "system") {
      const systemTheme = window.matchMedia("(prefers-color-scheme: dark)")
        .matches
        ? "dark"
        : "light";
      document.documentElement.classList.toggle("dark", systemTheme === "dark");
    } else {
      document.documentElement.classList.toggle("dark", theme === "dark");
    }

    onThemeChange?.(theme);
  }, [theme, onThemeChange]);

  // Apply reduced motion changes
  useEffect(() => {
    localStorage.setItem("reducedMotion", String(reducedMotion));
    document.documentElement.classList.toggle("reduce-motion", reducedMotion);
    onReducedMotionChange?.(reducedMotion);
  }, [reducedMotion, onReducedMotionChange]);

  // Apply high contrast changes
  useEffect(() => {
    localStorage.setItem("highContrast", String(highContrast));
    document.documentElement.classList.toggle("high-contrast", highContrast);
    onHighContrastChange?.(highContrast);
  }, [highContrast, onHighContrastChange]);

  // Apply accent color changes
  useEffect(() => {
    localStorage.setItem("accentColor", accentColor);
    document.documentElement.setAttribute("data-accent", accentColor);
  }, [accentColor]);

  const accentColors = [
    { name: "Blue", value: "blue", class: "bg-blue-500" },
    { name: "Green", value: "green", class: "bg-green-500" },
    { name: "Purple", value: "purple", class: "bg-purple-500" },
    { name: "Red", value: "red", class: "bg-red-500" },
    { name: "Orange", value: "orange", class: "bg-orange-500" },
    { name: "Pink", value: "pink", class: "bg-pink-500" },
  ];

  return (
    <div className={cn("space-y-6", className)}>
      <div>
        <h3 className="text-lg font-medium flex items-center gap-2">
          <Palette className="h-5 w-5" />
          Appearance
        </h3>
        <p className="text-sm text-muted-foreground">
          Customize the appearance of the application
        </p>
      </div>

      <Separator />

      <div className="space-y-4">
        <div>
          <h4 className="text-sm font-medium mb-3">Theme</h4>
          <div className="grid grid-cols-3 gap-2">
            <Button
              variant={theme === "light" ? "default" : "outline"}
              className="flex flex-col items-center justify-center gap-2 h-24"
              onClick={() => setTheme("light")}
            >
              <Sun className="h-6 w-6" />

              <span>Light</span>
              {theme === "light" && (
                <Check className="absolute top-2 right-2 h-4 w-4 text-primary-foreground" />
              )}
            </Button>
            <Button
              variant={theme === "dark" ? "default" : "outline"}
              className="flex flex-col items-center justify-center gap-2 h-24"
              onClick={() => setTheme("dark")}
            >
              <Moon className="h-6 w-6" />

              <span>Dark</span>
              {theme === "dark" && (
                <Check className="absolute top-2 right-2 h-4 w-4 text-primary-foreground" />
              )}
            </Button>
            <Button
              variant={theme === "system" ? "default" : "outline"}
              className="flex flex-col items-center justify-center gap-2 h-24"
              onClick={() => setTheme("system")}
            >
              <Monitor className="h-6 w-6" />

              <span>System</span>
              {theme === "system" && (
                <Check className="absolute top-2 right-2 h-4 w-4 text-primary-foreground" />
              )}
            </Button>
          </div>
        </div>

        <div>
          <h4 className="text-sm font-medium mb-3">Accent Color</h4>
          <RadioGroup
            value={accentColor}
            onValueChange={setAccentColor}
            className="grid grid-cols-3 sm:grid-cols-6 gap-2"
          >
            {accentColors.map((color) => (
              <div key={color.value} className="flex items-center space-x-2">
                <RadioGroupItem
                  value={color.value}
                  id={`color-${color.value}`}
                  className="sr-only"
                />

                <Label
                  htmlFor={`color-${color.value}`}
                  className={cn(
                    "h-8 w-full cursor-pointer rounded-md border-2 flex items-center justify-center",
                    accentColor === color.value
                      ? "border-primary"
                      : "border-transparent",
                  )}
                >
                  <span className={cn("h-6 w-6 rounded-full", color.class)} />
                </Label>
              </div>
            ))}
          </RadioGroup>
        </div>
      </div>

      <Separator />

      <div className="space-y-4">
        <div>
          <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
            <Sliders className="h-4 w-4" />
            Accessibility
          </h4>
        </div>

        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <Label htmlFor="reduced-motion">Reduced motion</Label>
            <p className="text-sm text-muted-foreground">
              Reduce the amount of animations
            </p>
          </div>
          <Switch
            id="reduced-motion"
            checked={reducedMotion}
            onCheckedChange={setReducedMotion}
          />
        </div>

        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <Label htmlFor="high-contrast">High contrast</Label>
            <p className="text-sm text-muted-foreground">
              Increase the contrast for better visibility
            </p>
          </div>
          <Switch
            id="high-contrast"
            checked={highContrast}
            onCheckedChange={setHighContrast}
          />
        </div>
      </div>

      <Separator />

      <div className="space-y-4">
        <div>
          <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
            <Zap className="h-4 w-4" />
            Performance
          </h4>
        </div>

        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <Label htmlFor="disable-animations">Disable animations</Label>
            <p className="text-sm text-muted-foreground">
              Turn off all animations for better performance
            </p>
          </div>
          <Switch id="disable-animations" />
        </div>
      </div>
    </div>
  );
}
