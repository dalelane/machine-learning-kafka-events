FROM node:12

WORKDIR /usr/src/app

COPY package*.json ./
RUN npm install

COPY run.js .

CMD [ "node", "run.js" ]


