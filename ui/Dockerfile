FROM node:24-alpine

WORKDIR /ui

COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile

COPY . .
RUN yarn build

ENTRYPOINT [ "yarn" ]
CMD [ "start" ]
