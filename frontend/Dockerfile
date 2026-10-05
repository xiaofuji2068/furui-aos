# Furui AI OS — 前端镜像（TASK-017 / 70-02）
# 构建：docker build -f frontend/Dockerfile -t furui-aios-frontend:2.0 .
# 运行时需注入 BACKEND_URL（容器编排内指向 http://backend:8000；见 docker-compose.yml）

FROM node:20-alpine AS deps
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY frontend/ ./
# 构建期后端地址仅影响 SSR 重写模板；运行时 BACKEND_URL 覆盖（next.config.js 读环境变量）
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000
COPY --from=builder /app/package.json /app/package-lock.json ./
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/next.config.js ./next.config.js

EXPOSE 3000
CMD ["npm", "start"]
