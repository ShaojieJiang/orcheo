import React from "react";
import { Check, Monitor, Moon, Palette, Sliders, Sun, Zap } from "lucide-react";

import { Button } from "@/design-system/ui/button";
import { Label } from "@/design-system/ui/label";
import { RadioGroup, RadioGroupItem } from "@/design-system/ui/radio-group";
import { Separator } from "@/design-system/ui/separator";
import { Switch } from "@/design-system/ui/switch";
import { cn } from "@/lib/utils";

import { useThemePreferences } from "./use-theme-preferences";

interface ThemeSettingsProps {
  onThemeChange?: (theme: "light" | "dark" | "system") => void;
  onReducedMotionChange?: (enabled: boolean) => void;
  onHighContrastChange?: (enabled: boolean) => void;
  className?: string;
}

const accentColors = [
  { name: "Blue", value: "blue", class: "bg-blue-500" },
  { name: "Green", value: "green", class: "bg-green-500" },
  { name: "Purple", value: "purple", class: "bg-purple-500" },
  { name: "Red", value: "red", class: "bg-red-500" },
  { name: "Orange", value: "orange", class: "bg-orange-500" },
  { name: "Pink", value: "pink", class: "bg-pink-500" },
];

export default function ThemeSettings({
  onThemeChange,
  onReducedMotionChange,
  onHighContrastChange,
  className,
}: ThemeSettingsProps) {
  const {
    accentColor,
    highContrast,
    reducedMotion,
    setAccentColor,
    setHighContrast,
    setReducedMotion,
    setTheme,
    theme,
  } = useThemePreferences({
    onThemeChange,
    onHighContrastChange,
    onReducedMotionChange,
  });

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
            <ThemeCard
              label="Light"
              icon={<Sun className="h-6 w-6" />}
              isActive={theme === "light"}
              onClick={() => setTheme("light")}
            />
            <ThemeCard
              label="Dark"
              icon={<Moon className="h-6 w-6" />}
              isActive={theme === "dark"}
              onClick={() => setTheme("dark")}
            />
            <ThemeCard
              label="System"
              icon={<Monitor className="h-6 w-6" />}
              isActive={theme === "system"}
              onClick={() => setTheme("system")}
            />
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
        <SectionHeader
          icon={<Sliders className="h-4 w-4" />}
          title="Accessibility"
        />

        <PreferenceToggle
          id="reduced-motion"
          label="Reduced motion"
          description="Reduce the amount of animations"
          checked={reducedMotion}
          onToggle={setReducedMotion}
        />

        <PreferenceToggle
          id="high-contrast"
          label="High contrast"
          description="Increase the contrast for better visibility"
          checked={highContrast}
          onToggle={setHighContrast}
        />
      </div>

      <Separator />

      <div className="space-y-4">
        <SectionHeader icon={<Zap className="h-4 w-4" />} title="Performance" />

        <PreferenceToggle
          id="disable-animations"
          label="Disable animations"
          description="Turn off all animations for better performance"
        />
      </div>
    </div>
  );
}

interface ThemeCardProps {
  label: string;
  icon: React.ReactNode;
  isActive: boolean;
  onClick: () => void;
}

const ThemeCard: React.FC<ThemeCardProps> = ({
  icon,
  isActive,
  label,
  onClick,
}) => (
  <Button
    variant={isActive ? "default" : "outline"}
    className="flex flex-col items-center justify-center gap-2 h-24"
    onClick={onClick}
  >
    {icon}
    <span>{label}</span>
    {isActive && (
      <Check className="absolute top-2 right-2 h-4 w-4 text-primary-foreground" />
    )}
  </Button>
);

interface PreferenceToggleProps {
  id: string;
  label: string;
  description: string;
  checked?: boolean;
  onToggle?: (checked: boolean) => void;
}

const PreferenceToggle: React.FC<PreferenceToggleProps> = ({
  checked,
  description,
  id,
  label,
  onToggle,
}) => {
  const switchProps =
    typeof checked === "boolean" ? { checked, onCheckedChange: onToggle } : {};

  return (
    <div className="flex items-center justify-between">
      <div className="space-y-0.5">
        <Label htmlFor={id}>{label}</Label>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
      <Switch id={id} {...switchProps} />
    </div>
  );
};

interface SectionHeaderProps {
  icon: React.ReactNode;
  title: string;
}

const SectionHeader: React.FC<SectionHeaderProps> = ({ icon, title }) => (
  <div>
    <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
      {icon}
      {title}
    </h4>
  </div>
);
