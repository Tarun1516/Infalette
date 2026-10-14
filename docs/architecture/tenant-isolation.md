# Tenant Isolation Strategy

Every tenant-owned database record contains a `tenant_id` column.

## Resolution

Tenant context is resolved from:
1. JWT token (authenticated requests)
2. Custom domain
3. Subdomain

## Enforcement

Tenant isolation is enforced in the data-access layer using tenant-scoped queries.
