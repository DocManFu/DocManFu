# =============================================================================
# DocManFu Production Frontend Image (multi-stage)
# Builds SvelteKit static SPA, serves via nginx with API proxy
# =============================================================================

# --- Stage 1: Build SPA ---
FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# --- Stage 2: Serve with nginx ---
FROM nginx:alpine

COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
