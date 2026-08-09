# DIO Market Command · Wave 2

Wave 2 turns Market Command from a governed campaign registry into a **read-first cross-channel marketing intelligence plane**.

## New in Wave 2

- Read-only adapters for Meta Ads, Reddit Ads, TikTok Ads and Google Ads reporting.
- External campaign binding: DIO campaign ID ↔ platform campaign ID.
- Normalized channel snapshots with evidence grades.
- Attribution spine for content, leads, orders, payments and jobs.
- Professional role bindings for LinkedIn/Apollo/public-source enrichment without converting identity into outreach permission.
- Cross-channel portfolio scoreboard based on verified DIO revenue.
- Governed campaign export packs for manual/native platform creation.
- South African publisher/agency procurement briefs.
- Hardened localhost control surface with Origin/Host guard and optional `DIO_MARKET_CONTROL_TOKEN`.
- Platform write adapters remain **disabled by design**.

## Install

```bash
unzip DIO_Market_Command_Wave2.zip
cd DIO_Market_Command_Wave2
python3 install_market_command.py --target /path/to/DIO
cd /path/to/DIO
PYTHONPATH=. python3 -m pytest -q tests/test_market_command.py tests/test_market_intelligence.py tests/test_marketing_adapters.py
python3 scripts/serve_market_command.py
```

Open `http://127.0.0.1:8770/`.

See `config/channel_connections.example.json` and `docs/WAVE2_READ_FIRST_CHANNELS.md` before configuring platform credentials.

## Optional visual demo

```bash
python3 scripts/seed_market_command_demo.py
```

The seed is explicitly simulated, zero-spend and non-publishable. It exists only to populate the dashboard for UI inspection.
