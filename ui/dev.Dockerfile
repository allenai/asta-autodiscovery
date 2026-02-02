FROM node:24-alpine

WORKDIR /ui

# Git is required because stdlib dependencies in the lockfile are fetched via git+https URLs.
# Python and build tools are required for node-gyp when stdlib builds native modules.
RUN apk add --no-cache git python3 make g++

COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile

COPY . .

ENTRYPOINT [ "yarn" ]
CMD [ "dev" ]
