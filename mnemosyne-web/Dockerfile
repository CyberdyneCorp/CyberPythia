FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci || npm install
COPY . .
RUN npm run build && npm prune --omit=dev

FROM node:22-alpine
RUN addgroup -S mnemosyne && adduser -S mnemosyne -G mnemosyne
WORKDIR /app
COPY --from=builder --chown=mnemosyne:mnemosyne /app/build ./build
COPY --from=builder --chown=mnemosyne:mnemosyne /app/node_modules ./node_modules
COPY --from=builder --chown=mnemosyne:mnemosyne /app/package.json ./
ENV NODE_ENV=production PORT=3000
USER mnemosyne
EXPOSE 3000
CMD ["node", "build"]
