# Canvas

Orcheo Canvas is the visual workflow designer for creating, visualizing, and managing workflows through a drag-and-drop interface.

## Installation

```bash
# Install globally
npm install -g orcheo-canvas

# Or install locally in your project
npm install orcheo-canvas
```

## Usage

After installation, start the Canvas interface:

```bash
# Start preview server (production mode)
orcheo-canvas

# Start development server
orcheo-canvas dev

# Build for production
orcheo-canvas build

# Preview production build
orcheo-canvas preview
```

The Canvas application will be available at:

- **Development mode**: `http://localhost:5173`
- **Production mode**: Configured preview port

## Configuration

Canvas connects to the Orcheo backend API. Configure the connection via environment variables:

```bash
# Backend API URL
VITE_ORCHEO_BACKEND_URL=http://localhost:8000

# Authentication (optional)
VITE_ORCHEO_AUTH_ISSUER=https://your-idp.com/
VITE_ORCHEO_AUTH_CLIENT_ID=your-client-id
```

## Docker Compose

When running the full stack with Docker Compose, Canvas is included automatically:

```bash
docker compose up -d
```

Canvas will be available at `http://localhost:5173`.

See [Manual Setup Guide](manual_setup.md#docker-compose-full-stack) for the complete Docker Compose setup.

## Features

- **Visual workflow builder**: Drag-and-drop nodes to create workflows
- **Real-time execution**: Watch workflows execute with live status updates
- **Node library**: Browse and add nodes from the built-in library
- **Workflow management**: Create, edit, delete, and version workflows
- **ChatKit integration**: Test conversational workflows directly in Canvas
- **Version awareness**: Top navigation shows Canvas + backend versions
- **Update reminders**: Non-blocking reminder appears when updates are available (checked at most once every 24 hours per browser profile)
