export class AuthManager {
  static setToken(token: string) {
    localStorage.setItem("access_token", token);
  }

  static getToken(): string | null {
    return localStorage.getItem("access_token");
  }

  static clearToken() {
    localStorage.removeItem("access_token");
  }

  static isAuthenticated(): boolean {
    return !!this.getToken();
  }
}
