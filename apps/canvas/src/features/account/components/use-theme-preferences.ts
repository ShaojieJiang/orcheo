import { useEffect, useState } from "react";

type ThemeOption = "light" | "dark" | "system";

interface UseThemePreferencesArgs {
  onThemeChange?: (theme: ThemeOption) => void;
  onReducedMotionChange?: (enabled: boolean) => void;
  onHighContrastChange?: (enabled: boolean) => void;
}

const isBrowser = () => typeof window !== "undefined";

const getSystemTheme = (): ThemeOption => {
  if (!isBrowser()) {
    return "light";
  }

  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
};

const getStoredTheme = (): ThemeOption => {
  if (!isBrowser()) {
    return "system";
  }

  return (localStorage.getItem("theme") as ThemeOption | null) ?? "system";
};

const getStoredBoolean = (key: string): boolean => {
  if (!isBrowser()) {
    return false;
  }

  return localStorage.getItem(key) === "true";
};

const getStoredAccentColor = (): string => {
  if (!isBrowser()) {
    return "blue";
  }

  return localStorage.getItem("accentColor") || "blue";
};

export const useThemePreferences = ({
  onThemeChange,
  onReducedMotionChange,
  onHighContrastChange,
}: UseThemePreferencesArgs) => {
  const [theme, setTheme] = useState<ThemeOption>(() => getStoredTheme());
  const [reducedMotion, setReducedMotion] = useState(() =>
    getStoredBoolean("reducedMotion"),
  );
  const [highContrast, setHighContrast] = useState(() =>
    getStoredBoolean("highContrast"),
  );
  const [accentColor, setAccentColor] = useState(() => getStoredAccentColor());

  useEffect(() => {
    if (!isBrowser()) {
      return;
    }

    localStorage.setItem("theme", theme);
    const nextTheme = theme === "system" ? getSystemTheme() : theme;
    document.documentElement.classList.toggle("dark", nextTheme === "dark");
    onThemeChange?.(theme);
  }, [theme, onThemeChange]);

  useEffect(() => {
    if (!isBrowser()) {
      return;
    }

    localStorage.setItem("reducedMotion", String(reducedMotion));
    document.documentElement.classList.toggle("reduce-motion", reducedMotion);
    onReducedMotionChange?.(reducedMotion);
  }, [reducedMotion, onReducedMotionChange]);

  useEffect(() => {
    if (!isBrowser()) {
      return;
    }

    localStorage.setItem("highContrast", String(highContrast));
    document.documentElement.classList.toggle("high-contrast", highContrast);
    onHighContrastChange?.(highContrast);
  }, [highContrast, onHighContrastChange]);

  useEffect(() => {
    if (!isBrowser()) {
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
