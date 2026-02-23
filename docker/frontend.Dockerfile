# Stage 1: Build
FROM node:20-alpine as build-stage

WORKDIR /app

# For prototype we assume standard structure
# If it's pure HTML/HTMX we might just need Nginx
# But let's follow the React/Tailwind assumption
COPY package*.json ./
RUN npm install

COPY . .
RUN npm run build

# Stage 2: Serve
FROM nginx:stable-alpine

COPY --from=build-stage /app/dist /usr/share/nginx/html
# If using HTMX/templates from backend, Nginx would be a reverse proxy
# For now assume static dashboard assets
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
