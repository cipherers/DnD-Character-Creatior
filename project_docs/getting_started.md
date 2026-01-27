# Getting Started with D&D Character Creator

This guide will help you set up the project locally for development.

## Prerequisites

1.  **Python 3.8+**: [Download Python](https://www.python.org/downloads/)
2.  **Node.js & npm**: [Download Node.js](https://nodejs.org/) (Required for Cloudflare Wrangler)
3.  **Git**: [Download Git](https://git-scm.com/)

## Installation

1.  **Clone the repository**:
    ```bash
    git clone <repository_url>
    cd DnD-Character-Creatior
    ```

2.  **Install Backend Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Install Worker Dependencies** (if you plan to edit the edge worker):
    ```bash
    npm install -g wrangler
    ```

## Local Development

### 1. Running the Backend (Flask)
The backend runs on Python/Flask.

```bash
# Navigate to the project root
# Linux/Mac
export FLASK_ENV=development
python Back-end/app.py

# Windows (PowerShell)
$env:FLASK_ENV = "development"
python Back-end/app.py
```
*The server will start at `http://localhost:5000`.*

> **Note**: In development mode (`FLASK_ENV=development` or `ENV=dev`), the specialized security checks (like `X-Proxy-Secret` and HTTPS enforcement) are disabled to make local testing easier.

### 2. Running the Frontend
The frontend is a static site located in `docs/`.

**Option A: Simple HTTP Server (Recommended)**
```bash
python -m http.server -d docs 8000
```
Open `http://localhost:8000` in your browser.

**Option B: VS Code Live Server**
If you use VS Code, install the "Live Server" extension, right-click `docs/index.html`, and choose "Open with Live Server".

### 3. Developing the Cloudflare Worker
The `index.js` file contains the logic for the Edge Middleware (Rate Limiting, Caching).

To run it locally using Wrangler:
```bash
npx wrangler dev
```
This will start a local instance of the Cloudflare Worker that proxies requests to your backend. You may need to update `config.js` in the frontend to point to this local worker URL (usually `http://localhost:8787`).

## Project Structure Overview

*   `Back-end/`: Python server code (`app.py`, `models.py`).
*   `docs/`: Frontend code (HTML, CSS, JS). This is what users see.
*   `index.js`: Cloudflare Worker script.
*   `project_docs/`: Documentation (You are here).

## Deployment

*   **Frontend**: Automatically deployed via **GitHub Pages** when you push changes to the `docs/` folder on the main branch.
*   **Backend**: Deployed to **Render**. It detects `requirements.txt` and uses `gunicorn` (specified in `Procfile`) to run the app.
*   **Edge**: Deployed to **Cloudflare Workers** using `wrangler deploy`.

## Common Tasks

**Adding a new dependency:**
1.  `pip install <package_name>`
2.  `pip freeze > requirements.txt`

**Resetting the Database**:
The database is an SQLite file `instance/site.db` (or `Back-end/site.db`). To reset it, simply delete the file and restart the Flask server; it will automatically recreate the tables and seed initial data.
