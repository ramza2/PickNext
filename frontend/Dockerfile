# PickNext Frontend — production multi-stage image
# Build: docker build --build-arg VITE_API_BASE_URL=/api/v1 -t picknext-frontend:dpl1 ./frontend
#
# Runtime serves static files only (no /api reverse proxy).
# Traefik will route / → Frontend and /api → Backend in later DPL steps.

# Node 22 matches README "Node.js 20+" and is a current LTS line for Vite 6.
FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG VITE_API_BASE_URL=/api/v1
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

RUN npm run build \
  && test -f dist/index.html

FROM nginx:1.28-alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
