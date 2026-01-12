FROM node:20-slim

# Install wget for health checks
RUN apt-get update && apt-get install -y wget && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy application code
COPY server.js ./
COPY public ./public

# Create results directory
RUN mkdir -p results

# Expose port
EXPOSE 3001

# Run the server
CMD ["node", "server.js"]
