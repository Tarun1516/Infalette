/**
 * @infalette/themes - Theme system for Infalette storefronts.
 */

// Theme types
export interface ThemeConfig {
  colors: ColorPalette;
  typography: TypographyScale;
  spacing: SpacingTokens;
  borderRadius: BorderRadiusTokens;
  shadows: ShadowTokens;
  breakpoints: BreakpointTokens;
}

export interface ColorPalette {
  primary: string;
  primaryForeground: string;
  secondary: string;
  secondaryForeground: string;
  background: string;
  foreground: string;
  muted: string;
  mutedForeground: string;
  accent: string;
  accentForeground: string;
  destructive: string;
  destructiveForeground: string;
  border: string;
  input: string;
  ring: string;
}

export interface TypographyScale {
  fontFamily: string;
  fontSize: {
    xs: string;
    sm: string;
    base: string;
    lg: string;
    xl: string;
    "2xl": string;
    "3xl": string;
    "4xl": string;
  };
  fontWeight: {
    normal: number;
    medium: number;
    semibold: number;
    bold: number;
  };
  lineHeight: {
    tight: number;
    normal: number;
    relaxed: number;
  };
}

export interface SpacingTokens {
  px: string;
  py: string;
  gap: {
    sm: string;
    md: string;
    lg: string;
    xl: string;
  };
}

export interface BorderRadiusTokens {
  sm: string;
  md: string;
  lg: string;
  full: string;
}

export interface ShadowTokens {
  sm: string;
  md: string;
  lg: string;
  xl: string;
}

export interface BreakpointTokens {
  sm: string;
  md: string;
  lg: string;
  xl: string;
  "2xl": string;
}

// Theme presets
export const defaultTheme: ThemeConfig = {
  colors: {
    primary: "#6366f1",
    primaryForeground: "#ffffff",
    secondary: "#8b5cf6",
    secondaryForeground: "#ffffff",
    background: "#ffffff",
    foreground: "#1f2937",
    muted: "#f3f4f6",
    mutedForeground: "#6b7280",
    accent: "#ec4899",
    accentForeground: "#ffffff",
    destructive: "#ef4444",
    destructiveForeground: "#ffffff",
    border: "#e5e7eb",
    input: "#e5e7eb",
    ring: "#6366f1",
  },
  typography: {
    fontFamily: "Inter, system-ui, sans-serif",
    fontSize: {
      xs: "0.75rem",
      sm: "0.875rem",
      base: "1rem",
      lg: "1.125rem",
      xl: "1.25rem",
      "2xl": "1.5rem",
      "3xl": "1.875rem",
      "4xl": "2.25rem",
    },
    fontWeight: {
      normal: 400,
      medium: 500,
      semibold: 600,
      bold: 700,
    },
    lineHeight: {
      tight: 1.25,
      normal: 1.5,
      relaxed: 1.75,
    },
  },
  spacing: {
    px: "1rem",
    py: "1rem",
    gap: {
      sm: "0.5rem",
      md: "1rem",
      lg: "1.5rem",
      xl: "2rem",
    },
  },
  borderRadius: {
    sm: "0.25rem",
    md: "0.5rem",
    lg: "0.75rem",
    full: "9999px",
  },
  shadows: {
    sm: "0 1px 2px 0 rgba(0,0,0,0.05)",
    md: "0 4px 6px -1px rgba(0,0,0,0.1)",
    lg: "0 10px 15px -3px rgba(0,0,0,0.1)",
    xl: "0 20px 25px -5px rgba(0,0,0,0.1)",
  },
  breakpoints: {
    sm: "640px",
    md: "768px",
    lg: "1024px",
    xl: "1280px",
    "2xl": "1536px",
  },
};

export const minimalTheme: ThemeConfig = {
  ...defaultTheme,
  colors: {
    ...defaultTheme.colors,
    primary: "#000000",
    primaryForeground: "#ffffff",
    secondary: "#374151",
    accent: "#6b7280",
  },
};

export const vibrantTheme: ThemeConfig = {
  ...defaultTheme,
  colors: {
    ...defaultTheme.colors,
    primary: "#ec4899",
    secondary: "#f59e0b",
    accent: "#10b981",
  },
};

// Theme utilities
export function applyTheme(theme: ThemeConfig): void {
  if (typeof document === "undefined") return;

  const root = document.documentElement;
  const { colors } = theme;

  root.style.setProperty("--color-primary", colors.primary);
  root.style.setProperty("--color-primary-foreground", colors.primaryForeground);
  root.style.setProperty("--color-secondary", colors.secondary);
  root.style.setProperty("--color-secondary-foreground", colors.secondaryForeground);
  root.style.setProperty("--color-background", colors.background);
  root.style.setProperty("--color-foreground", colors.foreground);
  root.style.setProperty("--color-muted", colors.muted);
  root.style.setProperty("--color-muted-foreground", colors.mutedForeground);
  root.style.setProperty("--color-accent", colors.accent);
  root.style.setProperty("--color-accent-foreground", colors.accentForeground);
  root.style.setProperty("--color-destructive", colors.destructive);
  root.style.setProperty("--color-destructive-foreground", colors.destructiveForeground);
  root.style.setProperty("--color-border", colors.border);
  root.style.setProperty("--color-input", colors.input);
  root.style.setProperty("--color-ring", colors.ring);
}

export function generateCssVariables(theme: ThemeConfig): string {
  const { colors } = theme;
  return `
:root {
  --color-primary: ${colors.primary};
  --color-primary-foreground: ${colors.primaryForeground};
  --color-secondary: ${colors.secondary};
  --color-secondary-foreground: ${colors.secondaryForeground};
  --color-background: ${colors.background};
  --color-foreground: ${colors.foreground};
  --color-muted: ${colors.muted};
  --color-muted-foreground: ${colors.mutedForeground};
  --color-accent: ${colors.accent};
  --color-accent-foreground: ${colors.accentForeground};
  --color-destructive: ${colors.destructive};
  --color-destructive-foreground: ${colors.destructiveForeground};
  --color-border: ${colors.border};
  --color-input: ${colors.input};
  --color-ring: ${colors.ring};
}
  `.trim();
}

export function getThemePreset(name: string): ThemeConfig {
  switch (name) {
    case "minimal":
      return minimalTheme;
    case "vibrant":
      return vibrantTheme;
    default:
      return defaultTheme;
  }
}