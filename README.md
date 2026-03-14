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
# Install dependencies
pip install -r requirements.txt

# Run the API server
uvicorn src.usdagent.api:app --reload

# Open http://localhost:8000/ui for the web UI
```

## API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/assets` | Create a new USD asset from a text description |
| GET | `/assets/{id}` | Retrieve an asset and its status |
| PATCH | `/assets/{id}/refine` | Iteratively refine an existing asset |
| GET | `/ui` | Web UI for asset viewer and Google Drive export |

See [docs/api.md](docs/api.md) for the full API spec.

## Architecture

See [docs/architecture.md](docs/architecture.md) for the high-level design.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

## License

Apache 2.0
