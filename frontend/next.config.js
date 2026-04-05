/**
 * Run `build` or `dev` with `SKIP_ENV_VALIDATION` to skip env validation. This is especially useful
 * for Docker builds.
 */
import "./src/env.js";

/** @type {import("next").NextConfig} */
const config = {
  devIndicators: false,
  async rewrites() {
    return [
      {
        source: "/api/langgraph/:path*",
        destination: `${process.env.NEXT_PUBLIC_LANGGRAPH_BASE_URL || "http://localhost:2024"}/:path*`,
      },
      {
        source: "/api/models",
        destination: `${process.env.NEXT_PUBLIC_BACKEND_BASE_URL || "http://localhost:8001"}/api/models`,
      },
      {
        source: "/api/memory",
        destination: `${process.env.NEXT_PUBLIC_BACKEND_BASE_URL || "http://localhost:8001"}/api/memory`,
      },
      {
        source: "/api/mcp",
        destination: `${process.env.NEXT_PUBLIC_BACKEND_BASE_URL || "http://localhost:8001"}/api/mcp`,
      },
      {
        source: "/api/skills",
        destination: `${process.env.NEXT_PUBLIC_BACKEND_BASE_URL || "http://localhost:8001"}/api/skills`,
      },
      {
        source: "/api/agents",
        destination: `${process.env.NEXT_PUBLIC_BACKEND_BASE_URL || "http://localhost:8001"}/api/agents`,
      },
      {
        source: "/api/threads/:path*",
        destination: `${process.env.NEXT_PUBLIC_BACKEND_BASE_URL || "http://localhost:8001"}/api/threads/:path*`,
      },
      {
        source: "/docs",
        destination: `${process.env.NEXT_PUBLIC_BACKEND_BASE_URL || "http://localhost:8001"}/docs`,
      },
      {
        source: "/redoc",
        destination: `${process.env.NEXT_PUBLIC_BACKEND_BASE_URL || "http://localhost:8001"}/redoc`,
      },
      {
        source: "/openapi.json",
        destination: `${process.env.NEXT_PUBLIC_BACKEND_BASE_URL || "http://localhost:8001"}/openapi.json`,
      },
      {
        source: "/health",
        destination: `${process.env.NEXT_PUBLIC_BACKEND_BASE_URL || "http://localhost:8001"}/health`,
      },
    ];
  },
};

export default config;
