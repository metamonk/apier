# Zapier Event Sender UI

A React web application for sending custom events to the Zapier Triggers API.

## Features

- 📝 **Event Submission Form**: Create custom events with any event type and JSON payload
- ✅ **Response Display**: See immediate feedback when events are created
- 🔄 **Real-time Polling**: Poll the inbox to see pending events
- 🎨 **Modern UI**: Clean, responsive design with gradient styling
- 📦 **Preset Examples**: Quick-start with example event templates

## Getting Started

### Prerequisites

- Node.js 18+
- pnpm (or npm/yarn)
- API Key from the deployed Zapier API

### Installation

1. Install dependencies:
   ```bash
   pnpm install
   ```

2. Configure environment variables:
   ```bash
   cp .env.example .env
   ```

3. Edit `.env` and add your API key:
   ```env
   VITE_API_URL=https://your-api-url.lambda-url.region.on.aws
   VITE_API_KEY=your_api_key_here
   ```

### Development

Start the development server:

```bash
pnpm dev
```

The app will be available at `http://localhost:3000`

### Build for Production

```bash
pnpm build
```

The built files will be in the `dist/` directory.

### Preview Production Build

```bash
pnpm preview
```

## Usage

### Creating an Event

1. Enter an event type (e.g., `user.signup`, `order.completed`)
2. Add your JSON payload in the textarea
3. Or use one of the preset examples:
   - 📝 User Signup
   - 🛒 Order Completed
   - ⚡ Custom Event
4. Click "Send Event"
5. View the response showing event ID and status

### Viewing Inbox Events

1. Click "Start Polling" to begin auto-refreshing the inbox
2. See all pending events that haven't been acknowledged yet
3. Events show their type, status, timestamp, and payload
4. Click "Pause Polling" to stop auto-refresh

## Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── EventForm.tsx      # Event submission form component
│   │   └── EventList.tsx      # Event inbox list component
│   ├── App.tsx                # Main app component with polling logic
│   ├── App.css                # App-specific styles
│   ├── main.tsx               # App entry point
│   └── style.css              # Global styles
├── .env                       # Environment configuration (gitignored)
├── .env.example               # Example environment file
├── index.html                 # HTML template
├── package.json               # Dependencies
├── tsconfig.json              # TypeScript config
└── vite.config.ts             # Vite config
```

## API Integration

The UI integrates with the Zapier Triggers API:

1. **Authentication**: Uses API key to get JWT token (`POST /token`)
2. **Event Creation**: Sends events with JWT auth (`POST /events`)
3. **Inbox Polling**: Retrieves pending events (`GET /inbox`)

All API calls use the JWT token for authentication after initial key exchange.

## Technology Stack

- **React 19**: Modern React with hooks
- **TypeScript**: Type-safe development
- **Vite**: Fast build tool and dev server
- **AWS Amplify**: Backend integration (optional)

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `VITE_API_URL` | Base URL of the deployed API | `https://xxx.lambda-url.us-east-2.on.aws` |
| `VITE_API_KEY` | API key for authentication | `your-base64-key` |

## License

ISC
