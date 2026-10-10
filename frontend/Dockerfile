FROM node:20-alpine

WORKDIR /app

COPY package.json ./
RUN npm config set fetch-retry-maxtimeout 120000 \
    && npm config set fetch-timeout 60000 \
    && npm install

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
