/** @type {import('next').NextConfig} */
const nextConfig = {
	output: 'standalone',
	async rewrites() {
		const apiOrigin = process.env.API_ORIGIN;
		if (!apiOrigin) return [];
		return [
			{
				source: '/api/:path*',
				destination: `${apiOrigin}/api/:path*`,
			},
		];
	},
};

module.exports = nextConfig;
