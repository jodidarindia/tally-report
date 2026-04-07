FROM node:18-alpine AS build

WORKDIR /app

COPY package.json ./

# Remove emergent-specific dev dependency not needed for self-hosted build
RUN node -e " \
  const pkg = JSON.parse(require('fs').readFileSync('package.json','utf8')); \
  if(pkg.devDependencies) delete pkg.devDependencies['@emergentbase/visual-edits']; \
  require('fs').writeFileSync('package.json', JSON.stringify(pkg, null, 2));" && \
  yarn install --network-timeout 600000

COPY . .

ARG REACT_APP_BACKEND_URL
ENV REACT_APP_BACKEND_URL=$REACT_APP_BACKEND_URL

RUN yarn build

FROM nginx:alpine
COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
