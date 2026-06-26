# Guardian AI — Setup Guide

## Run backend (Flask, no Jupyter required)

```powershell
cd "C:\Users\user\Downloads\AI (3)\AI"
pip install -r requirements.txt
python ml/train_model.py --max-rows 80000
python run_backend.py
```

Test: http://localhost:5000/health

## Run frontend (React + Vite)

```powershell
cd "C:\Users\user\Downloads\AI (3)\AI\frontend"
npm install
npm run dev
```

Open: http://localhost:5173

Set API URL in `frontend/.env`:

```
VITE_API_URL=http://localhost:5000
```

## API endpoints (backward compatible)

| Endpoint | Description |
|----------|-------------|
| `POST /login` | Auth (unchanged) |
| `POST /chat_predict` | Chat + enhanced JSON (`risk_score`, `explanation`, `confidence_score`, `trend_indicator`) |
| `GET /api/heatmap` | Heatmap points — filters: `area`, `crime_type`, `date_from`, `date_to`, `refresh=1` |
| `GET /api/analytics/dashboard` | Dashboard stats |
| `GET /api/analytics/trends` | Monthly trends |
| `GET /api/analytics/areas` | Area + crime distribution |
| `POST /api/heatmap/invalidate` | Clear heatmap cache after new cases |

## Enhancements (v2)

- **Heatmap**: Leaflet heat layer (green → yellow → red), CSV + live SQLite cases, auto-refresh every 60s
- **ML**: Random Forest classifier retained; added risk regressor (0–100), feature engineering (severity, recency, area frequency, trend)
- **UI**: SaaS dashboard, dark/light mode, sidebar nav, Recharts analytics, ChatGPT-style assistant with risk cards

## Notebook workflow

Run cells **1 → 2 → 3 → 4 → 5 → 6** in `Copy_of_GuardianAI_Secured_Final.ipynb` if you prefer Jupyter; `run_backend.py` is equivalent for Cell 5+.
