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

# Copy storefront app
COPY apps/storefront/ ./apps/storefront/

# Install dependencies
RUN pnpm install --frozen-lockfile

# Build shared packages
RUN pnpm --filter @infalette/ui... build || true
RUN pnpm --filter @infalette/themes... build || true
RUN pnpm --filter @infalette/page-builder... build || true

# Build the storefront
RUN pnpm --filter storefront build

# Production image
FROM node:22-alpine AS production

WORKDIR /app

# Copy root files
COPY package.json pnpm-workspace.yaml turbo.json ./

# Copy shared packages
COPY packages/ui/ ./packages/ui/
COPY packages/themes/ ./packages/themes/
COPY packages/page-builder/ ./packages/page-builder/

# Copy storefront app
COPY apps/storefront/ ./apps/storefront/

# Install only production dependencies
RUN npm install -g pnpm && \
    pnpm install --prod --frozen-lockfile

# Copy built output from builder
COPY --from=base /app/apps/storefront/.next ./apps/storefront/.next

EXPOSE 3000

CMD ["pnpm", "--filter", "storefront", "start"]
