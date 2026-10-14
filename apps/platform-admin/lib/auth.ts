export class AuthManager {
  static setToken(token: string) {
    if (typeof window !== "undefined") {
      localStorage.setItem("access_token", token);
    }
  }

  static getToken(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("access_token");
  }

  static clearToken() {
    if (typeof window !== "undefined") {
      localStorage.removeItem("access_token");
    }
  }

  static isAuthenticated(): boolean {
    return !!this.getToken();
  }
}
