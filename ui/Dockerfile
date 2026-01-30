FROM node:24-alpine

WORKDIR /ui

# Git is required for @stdlib dependencies that resolve via git during yarn install.
RUN apk add --no-cache git

COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile

COPY . .
RUN yarn build

ENTRYPOINT [ "yarn" ]
CMD [ "start" ]
