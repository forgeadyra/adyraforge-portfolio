# syntax=docker/dockerfile:1
# Local development image. Production is built and served by Netlify.
FROM node:22-alpine AS dev
ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN mkdir -p .next && chown -R node:node .next
USER node
EXPOSE 3000
HEALTHCHECK --interval=10s --timeout=5s --start-period=90s --retries=5 \
    CMD ["node", "-e", "fetch('http://127.0.0.1:3000/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"]
CMD ["npx", "next", "dev", "-H", "0.0.0.0", "-p", "3000"]
