# =============================================================================
# DocManFu Production Frontend Image (multi-stage)
# Builds SvelteKit static SPA, serves via nginx with API proxy
# =============================================================================

# --- Stage 1: Build SPA ---
# The output is static files, so build once on the native platform even when
# producing images for other architectures
FROM --platform=$BUILDPLATFORM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# --- Stage 2: Serve with nginx ---
FROM nginx:1.30-alpine

COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf
COPY security-headers.conf trusted-proxies.conf /etc/nginx/

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
