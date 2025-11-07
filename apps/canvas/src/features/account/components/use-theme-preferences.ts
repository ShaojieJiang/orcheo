import { useEffect, useState } from "react";

type ThemeOption = "light" | "dark" | "system";

interface UseThemePreferencesArgs {
  onThemeChange?: (theme: ThemeOption) => void;
  onReducedMotionChange?: (enabled: boolean) => void;
  onHighContrastChange?: (enabled: boolean) => void;
}

const getSystemTheme = (): ThemeOption => {
  if (typeof window === "undefined") {
    return "light";
  }

  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
};

export const useThemePreferences = ({
  onThemeChange,
  onReducedMotionChange,
  onHighContrastChange,
}: UseThemePreferencesArgs) => {
  const [theme, setTheme] = useState<ThemeOption>("system");
  const [reducedMotion, setReducedMotion] = useState(false);
  const [highContrast, setHighContrast] = useState(false);
  const [accentColor, setAccentColor] = useState("blue");

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const savedTheme =
      (localStorage.getItem("theme") as ThemeOption | null) ?? "system";
    setTheme(savedTheme);

    const initialTheme =
      savedTheme === "system" ? getSystemTheme() : savedTheme;
    document.documentElement.classList.toggle("dark", initialTheme === "dark");

    const savedReducedMotion = localStorage.getItem("reducedMotion") === "true";
    setReducedMotion(savedReducedMotion);

    const savedHighContrast = localStorage.getItem("highContrast") === "true";
    setHighContrast(savedHighContrast);

    const savedAccentColor = localStorage.getItem("accentColor") || "blue";
    setAccentColor(savedAccentColor);
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    localStorage.setItem("theme", theme);
    const nextTheme = theme === "system" ? getSystemTheme() : theme;
    document.documentElement.classList.toggle("dark", nextTheme === "dark");
    onThemeChange?.(theme);
  }, [theme, onThemeChange]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    localStorage.setItem("reducedMotion", String(reducedMotion));
    document.documentElement.classList.toggle("reduce-motion", reducedMotion);
    onReducedMotionChange?.(reducedMotion);
  }, [reducedMotion, onReducedMotionChange]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    localStorage.setItem("highContrast", String(highContrast));
    document.documentElement.classList.toggle("high-contrast", highContrast);
    onHighContrastChange?.(highContrast);
  }, [highContrast, onHighContrastChange]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    localStorage.setItem("accentColor", accentColor);
    document.documentElement.setAttribute("data-accent", accentColor);
  }, [accentColor]);

  return {
    accentColor,
    highContrast,
    reducedMotion,
    setAccentColor,
    setHighContrast,
    setReducedMotion,
    setTheme,
    theme,
  };
};
