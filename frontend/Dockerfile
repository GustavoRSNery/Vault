# Build do frontend e entrega estática por nginx.
# Duas etapas: o Node só existe na primeira, então a imagem final carrega
# apenas os arquivos compilados — sem node_modules, sem toolchain.

FROM node:22-alpine AS build

WORKDIR /app

# package.json antes do código: alterar uma tela não reinstala tudo.
COPY package.json package-lock.json ./
RUN npm ci

COPY tsconfig.json vite.config.ts index.html ./
COPY src ./src

# `npm run build` roda tsc antes do vite: erro de tipo derruba a imagem aqui,
# em vez de virar tela quebrada em produção.
RUN npm run build


FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://127.0.0.1/ || exit 1
