FROM node:24-slim

WORKDIR /ui

# Git is required for @stdlib dependencies that resolve via git during yarn install.
# Python/make/g++ are required by node-gyp for native addons during yarn install.
# ca-certificates is required for git+https yarn dependencies.
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates git python3 make g++

COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile

COPY . .
RUN yarn build

ENTRYPOINT [ "yarn" ]
CMD [ "start" ]
