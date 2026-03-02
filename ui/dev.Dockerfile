FROM node:24-slim

WORKDIR /ui

# Git is required because stdlib dependencies in the lockfile are fetched via git+https URLs.
# Python and build tools are required for node-gyp when stdlib builds native modules.
# ca-certificates is required for git+https yarn dependencies.
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates git python3 make g++ wget

COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile

COPY . .

ENTRYPOINT [ "yarn" ]
CMD [ "dev" ]
