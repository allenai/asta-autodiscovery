FROM node:24-alpine

WORKDIR /ui

# Git is required for @stdlib dependencies that resolve via git during yarn install.
# Python/make/g++ are required by node-gyp for native addons during yarn install.
RUN apk add --no-cache git python3 make g++

COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile

COPY . .
RUN yarn build

ENTRYPOINT [ "yarn" ]
CMD [ "start" ]
