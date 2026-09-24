FROM node:24-slim AS build

WORKDIR /ui

# Git is required for @stdlib dependencies that resolve via git during yarn install.
# Python/make/g++ are required by node-gyp for native addons during yarn install.
# ca-certificates is required for git+https yarn dependencies.
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates git python3 make g++

COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile

COPY . .
RUN yarn build

# Vite emits a static SPA; nginx serves it with an index.html fallback for client-side routes.
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /ui/dist /usr/share/nginx/html
EXPOSE 3000
