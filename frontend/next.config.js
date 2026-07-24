/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/:path*',
      },
    ]
  },
  
  images: {
    remotePatterns: [
      {
        protocol: 'http',
        hostname: 'localhost',
        port: '8000',
      },
      {
        protocol: 'https',
        hostname: '**',
      },
    ],
  },
  
  // ❌ Remove turbopack for Next.js 14
  // turbopack: {
  //   root: process.cwd(),
  // },
  
  experimental: {
    optimizeCss: true,
  },
}

module.exports = nextConfig