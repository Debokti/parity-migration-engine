# Northstar Drawdown MFE (Angular 17, application builder).
# Stage 1 builds the production bundle; stage 2 serves it via nginx with a
# backend reverse-proxy that mirrors proxy.conf.json (relative URLs unchanged).
ARG NODE_VERSION=22-alpine

FROM node:${NODE_VERSION} AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build:prod

FROM nginx:1.27-alpine AS runtime
# Application builder emits browser/ under the configured output path.
COPY --from=build /app/dist/target-angular/browser/ /usr/share/nginx/html/
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
ENV BACKEND_ORIGIN=http://backend:8080
EXPOSE 80
# nginx image entrypoint renders /etc/nginx/templates/*.template with envsubst.
CMD ["nginx", "-g", "daemon off;"]
