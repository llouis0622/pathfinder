# 빌드 컨텍스트: 레포 루트
FROM node:20-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --no-audit --no-fund
COPY frontend/ .
ARG VITE_VWORLD_KEY=
ARG VITE_BASEMAP_STYLE_URL=
ENV VITE_VWORLD_KEY=$VITE_VWORLD_KEY VITE_BASEMAP_STYLE_URL=$VITE_BASEMAP_STYLE_URL VITE_BACKEND_URL=
RUN npm run build

FROM nginx:1.27-alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
