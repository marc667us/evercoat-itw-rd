# EvercoatITWRD APP — web image
#
# NEXT_PUBLIC_* is BAKED IN AT BUILD TIME. Setting it as a runtime env var
# in compose has no effect on the bundle — the value is inlined during
# `next build`. It is therefore an ARG here, not just an ENV. This has
# caused real "the config is right but the app points at the wrong API"
# incidents; the comment is here so the next person does not rediscover it.

FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
# npm ci needs a lockfile; fall back to install on first bootstrap before
# one exists, so the image builds from a clean checkout.
RUN npm ci 2>/dev/null || npm install


FROM node:22-alpine AS builder
WORKDIR /app

ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_KEYCLOAK_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_PUBLIC_KEYCLOAK_URL=$NEXT_PUBLIC_KEYCLOAK_URL \
    NEXT_TELEMETRY_DISABLED=1

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# NODE_ENV=production explicitly. Building with NODE_ENV=development
# silently ships the development React runtime — slower, larger, and with
# different behaviour than what was tested.
ENV NODE_ENV=production
RUN npm run build


FROM node:22-alpine AS runtime
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000

RUN addgroup --system --gid 1001 nodejs \
 && adduser --system --uid 1001 nextjs

# Standalone output: server plus only the modules actually reached.
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

USER nextjs
EXPOSE 3000

CMD ["node", "server.js"]
