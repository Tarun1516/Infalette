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

# Copy platform-admin app
COPY apps/platform-admin/ ./apps/platform-admin/

# Install dependencies
RUN pnpm install --frozen-lockfile

# Build shared packages
RUN pnpm --filter @infalette/ui... build || true
RUN pnpm --filter @infalette/themes... build || true
RUN pnpm --filter @infalette/page-builder... build || true

# Build the platform-admin
RUN pnpm --filter platform-admin build

# Production image
FROM node:22-alpine AS production

WORKDIR /app

# Copy root files
COPY package.json pnpm-workspace.yaml turbo.json ./

# Copy shared packages
COPY packages/ui/ ./packages/ui/
COPY packages/themes/ ./packages/themes/
COPY packages/page-builder/ ./packages/page-builder/

# Copy platform-admin app
COPY apps/platform-admin/ ./apps/platform-admin/

# Install only production dependencies
RUN npm install -g pnpm && \
    pnpm install --prod --frozen-lockfile

# Copy built output from builder
COPY --from=base /app/apps/platform-admin/.next ./apps/platform-admin/.next

EXPOSE 3002

CMD ["pnpm", "--filter", "platform-admin", "start"]
