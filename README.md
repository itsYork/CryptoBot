# crypto-sentiment-edge

Real‑time crypto sentiment pipeline that merges news, Reddit, and order‑book snapshots, scores them with OpenAI GPT, trains a LightGBM model, and serves a Streamlit dashboard.

## Quick start

```bash
git clone <repo>
cd crypto-sentiment-edge
python -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env   # add keys
python run.py          # collector
streamlit run src/dashboard/app.py
```

## Packaging

Build wheel:

```bash
python -m build
```

Run tests and lint:

```bash
pip install -r requirements-dev.txt
pytest
ruff src tests
```
