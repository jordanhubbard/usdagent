NOTE:  This is a test project only!  It exists just to test some workflows and agent assignments over slack.  Please ignore unless you like looking at in-flight demos of agentic coding flows!

# usdagent

**USD Asset Generation API** — creates USD assets from text descriptions via API, supports iterative refinement, web UI with Google Drive integration.

## Overview

usdagent is an open-source service that lets you generate Universal Scene Description (USD) 3D assets from plain-text descriptions. It exposes a REST API for programmatic access and a web UI for interactive use.

Key features:
- **Text-to-USD generation**: POST a description, get back a USD file
- **Iterative refinement**: PATCH an existing asset with feedback to improve it
- **Web viewer**: Preview generated USD assets in your browser
- **Google Drive export**: One-click export to Google Drive

## Quick Start

```bash
# Create venv and install dependencies
make install-dev

# Run the API server with auto-reload
make dev

# Open http://localhost:8000/ui for the web UI
```

Run `make help` to see all available targets.

## Google Drive Setup

To enable the **Export to Drive** feature you need a Google Cloud OAuth 2.0 client.

### 1. Create OAuth credentials

1. Go to the [Google Cloud Console](https://console.cloud.google.com/) and select (or create) a project.
2. Enable the **Google Drive API**: APIs & Services → Library → search "Google Drive API" → Enable.
3. Go to **APIs & Services → Credentials → Create Credentials → OAuth client ID**.
4. Choose **Web application**.
5. Under **Authorized redirect URIs** add:
   ```
   http://localhost:8000/auth/google/callback
   ```
   (Add your production URL here when deploying.)
6. Download the credentials JSON or copy the **Client ID** and **Client Secret**.

### 2. Set environment variables

```bash
export GOOGLE_CLIENT_ID="your-client-id.apps.googleusercontent.com"
export GOOGLE_CLIENT_SECRET="your-client-secret"
```

Or add them to a `.env` file (never commit this file).

### 3. OAuth flow

| Step | What happens |
|------|-------------|
| User clicks **Export to Drive** | Browser redirects to `/auth/google` |
| Google consent screen | User grants Drive file access |
| Callback | Server stores credentials in-memory for the session |
| Export | Asset `.usda` file is uploaded; a link to the file is shown |

> **Note:** Credentials are stored in-memory only and are lost on server restart. For production, persist them in a database or secrets manager.

## API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/assets` | Create a new USD asset from a text description |
| GET | `/assets/{id}` | Retrieve an asset and its status |
| PATCH | `/assets/{id}/refine` | Iteratively refine an existing asset |
| GET | `/ui` | Web UI for asset viewer and Google Drive export |
| GET | `/auth/google` | Initiate Google OAuth2 flow |
| GET | `/auth/google/callback` | OAuth2 callback (handled automatically) |
| GET | `/auth/google/status` | Returns `{"authenticated": bool}` |
| POST | `/assets/{id}/export/drive` | Upload asset to authenticated user's Drive |

See [docs/api.md](docs/api.md) for the full API spec.

## Architecture

See [docs/architecture.md](docs/architecture.md) for the high-level design.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

## License

Apache 2.0
