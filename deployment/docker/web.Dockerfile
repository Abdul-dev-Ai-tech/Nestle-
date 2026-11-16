# Builds the React app and serves it with Caddy, which also reverse-proxies /api to the backend
# and obtains HTTPS certificates automatically when SITE_ADDRESS is a real domain.
FROM node:22-alpine AS build
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM caddy:2-alpine
COPY deployment/docker/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /src/dist /srv
EXPOSE 80 443
