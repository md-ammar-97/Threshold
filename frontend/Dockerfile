# Development image: runs `vite`. docker-compose.yml bind-mounts the
# source over this and uses an anonymous volume for node_modules so the
# Linux-built native deps aren't clobbered by the Windows/macOS host.
FROM node:22-slim

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm install

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev"]
