# MarketResearch — Kite Connect Dashboard

React + Vite frontend with a Python FastAPI backend for Zerodha Kite Connect login.

The **access token stays on the server** (saved to `backend/.kite_session.json`) and is never sent to the browser. During local development the backend restores that session on startup so you do not need to log in again after every code change.

---

## Project layout

```
MarketResearch/
├── backend/                 # FastAPI + Kite Connect
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── schemas.py
│   │   ├── routes/
│   │   └── services/
│   ├── requirements.txt
│   └── .kite_session.json   # created after login (gitignored)
├── frontend/                # React + Vite (TypeScript)
└── credentials.txt          # optional local notes (do not commit secrets)
```

---

## Prerequisites

- Python 3.10+
- Node.js 18+
- A Zerodha Kite Connect app (API key + API secret)

---

## 1. Backend setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API docs: http://127.0.0.1:8000/docs

### Useful endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/auth/login` | Exchange request token → access token (saved server-side) |
| `GET`  | `/api/auth/status` | Is a session already restored? |
| `POST` | `/api/auth/logout` | Clear in-memory + saved session |
| `GET`  | `/api/profile` | User name, ID, products, exchanges |
| `POST` | `/api/signals/sma-crossover` | Nifty 100 SMA crossover scan |

Login body example:

```json
{
  "api_key": "...",
  "api_secret": "...",
  "request_token": "..."
}
```

The response never includes `access_token`.

---

## 2. Frontend setup

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open: http://localhost:5173

Vite proxies `/api/*` to `http://127.0.0.1:8000`.

---

## 3. How to log in

1. Open Kite login in a browser:

   `https://kite.zerodha.com/connect/login?v=3&api_key=YOUR_API_KEY`

2. After approval, Zerodha redirects to your app redirect URL with `?request_token=...`
3. Paste **API Key**, **API Secret**, and **Request Token** on the Login page
4. Click **Login** → you land on the Dashboard
5. Open the **User** tab to see profile fields from Kite

Request tokens expire quickly and can be used only once.

---

## Session reuse (local development)

After a successful login, the backend writes:

`backend/.kite_session.json`

On the next `uvicorn` start (or reload), it tries to restore that session by calling Kite `profile()`. If the token is still valid, `/api/auth/status` reports `authenticated: true` and the frontend skips the login page.

Logout deletes this file.

> Note: Zerodha access tokens typically last until ~6 AM IST the next trading day. After that you must log in again with a fresh request token.

---

## Customizing the dark UI

Edit CSS variables in:

`frontend/src/styles/theme.css`

Examples:

- `--accent` — primary highlight color
- `--bg` / `--bg-panel` — page and panel backgrounds
- `--font` — typography

---

## Security notes

- Never commit `backend/.kite_session.json`, `credentials.txt`, or API secrets
- Do not log or display the access token in the frontend
- This setup is intended for **local development**
