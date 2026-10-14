export function getTenantFromHost(host: string): string {
  const parts = host.split(".");
  return parts[0] || "default";
}

export function getTenantUrl(tenant: string): string {
  return `https://${tenant}.infalette.com`;
}
