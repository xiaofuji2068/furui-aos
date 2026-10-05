/** @type {import('next').NextConfig} */
const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

const nextConfig = {
  reactStrictMode: true,
  // 构建校验用独立目录：dev server 常驻时二者不抢同一个 .next，
  // 也就不会在构建阶段触发批量删除保护。默认仍是 .next，不影响 dev/start。
  distDir: process.env.NEXT_DIST_DIR || ".next",
  async rewrites() {
    return [
      // TASK-017：后端地址环境化（容器内 BACKEND_URL=http://backend:8000；本机默认 127.0.0.1:8000）
      { source: "/api/backend/:path*", destination: `${BACKEND_URL}/api/:path*` },
    ];
  },
};
module.exports = nextConfig;
