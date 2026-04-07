FROM node:18-alpine AS build

WORKDIR /app

COPY package.json ./

# Remove emergent-specific dev dependency that's not needed for production build
RUN sed -i '/@emergentbase\/visual-edits/d' package.json && \
    yarn install --network-timeout 600000 || yarn install --network-timeout 600000

COPY . .

ARG REACT_APP_BACKEND_URL
ENV REACT_APP_BACKEND_URL=$REACT_APP_BACKEND_URL

RUN yarn build

FROM nginx:alpine
COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
