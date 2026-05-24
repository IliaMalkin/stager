/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  experimental: {
    serverActions: { allowedOrigins: ['localhost:3000', 'stager.kudnever.dev'] },
  },
  async rewrites() {
    // Поход с клиента/SSR в /api/v1/* через тот же origin —
    // в dev пробрасываем напрямую к api контейнеру.
    if (process.env.NODE_ENV === 'development') {
      return [
        { source: '/api/v1/:path*', destination: `${process.env.INTERNAL_API_BASE || 'http://api:8000'}/api/v1/:path*` },
      ];
    }
    return [];
  },
};

module.exports = nextConfig;
