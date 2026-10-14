FROM node:22-alpine AS base

# Install pnpm
RUN npm install -g pnpm

WORKDIR /app

# Copy root files
COPY package.json pnpm-workspace.yaml turbo.json ./

# Copy shared packages
COPY packages/ui/ ./packages/ui/
COPY packages/themes/ ./packages/themes/
COPY packages/page-builder/ ./packages/page-builder/

# Copy admin app
COPY apps/admin/ ./apps/admin/

# Install dependencies
RUN pnpm install --frozen-lockfile

# Build shared packages
RUN pnpm --filter @infalette/ui... build || true
RUN pnpm --filter @infalette/themes... build || true
RUN pnpm --filter @infalette/page-builder... build || true

# Build the admin
RUN pnpm --filter admin build

# Production image
FROM node:22-alpine AS production

WORKDIR /app

# Copy root files
COPY package.json pnpm-workspace.yaml turbo.json ./

# Copy shared packages
COPY packages/ui/ ./packages/ui/
COPY packages/themes/ ./packages/themes/
COPY packages/page-builder/ ./packages/page-builder/

# Copy admin app
COPY apps/admin/ ./apps/admin/

# Install only production dependencies
RUN npm install -g pnpm && \
    pnpm install --prod --frozen-lockfile

# Copy built output from builder
COPY --from=base /app/apps/admin/.next ./apps/admin/.next

EXPOSE 3001

CMD ["pnpm", "--filter", "admin", "start"]
