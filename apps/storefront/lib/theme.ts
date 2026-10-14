export interface ThemeConfig {
  colors: {
    primary: string;
    secondary: string;
    background: string;
    text: string;
  };
  typography: {
    heading: string;
    body: string;
  };
}

export const defaultTheme: ThemeConfig = {
  colors: {
    primary: "#3b82f6",
    secondary: "#64748b",
    background: "#ffffff",
    text: "#1e293b",
  },
  typography: {
    heading: "Inter, sans-serif",
    body: "Inter, sans-serif",
  },
};

export function applyTheme(theme: Partial<ThemeConfig>) {
  const merged = { ...defaultTheme, ...theme };
  document.documentElement.style.setProperty("--color-primary", merged.colors.primary);
  document.documentElement.style.setProperty("--color-secondary", merged.colors.secondary);
  document.documentElement.style.setProperty("--color-background", merged.colors.background);
  document.documentElement.style.setProperty("--color-text", merged.colors.text);
}
