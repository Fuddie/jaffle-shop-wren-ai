# Jaffle Shop analytics snapshot

A static browser dashboard using the dbt Jaffle Shop sample dataset and the existing Wren semantic layer. All displayed analyses execute through Wren in the browser. No application backend or warehouse connection is shipped.

## Local preview

From the Wren project root, run this one supported command:

```powershell
$env:PYTHONIOENCODING = 'utf-8'
& ..\.venv\Scripts\python.exe -B apps\jaffle-shop-analytics\local_service.py
```

Open **http://127.0.0.1:4174/**. This single loopback service serves the dashboard and the question API. It binds only to `127.0.0.1`. The older static-only preview at `http://127.0.0.1:4173/` remains a fallback and now discovers the service on port 4174 when that service is running. Do not start both commands for the normal Ask Wren workflow.

The pinned Wren WebAssembly engine loads from unpkg and requires internet access; the sample data is bundled locally. The first engine download can take a moment.

## Files and governance

- `mdl.json` is a byte-for-byte copy of the project's compiled MDL.
- `data/*.parquet` contains exports queried through the governed customers, orders, and payments models. The physical snapshot filename for payments is `stg_payments.parquet`.
- `queries.mjs` is the shared SQL source for the dashboard and validation workflow. Filters are allowlisted against this fixed sample's months and statuses.
- `validation.json` records 128 successful Wren queries across 30 filter combinations, snapshot export time, baseline results, and SQL.
- `app.mjs` registers the Parquet data in browser memory, loads the unchanged MDL, executes queries, and renders the interface.

Monthly analysis uses `monthly_order_summary` when no status is selected. Filtered monthly results and order KPIs use the exact expressions in `order_metrics`. Customer analysis uses `orders_customers`; orphan and amount checks also use the `payments_orders` join condition. Payments are aggregated before comparison to order amounts.

Order KPIs, monthly performance, top customers, and status analysis follow both filters. Customer and payment inventory counts, data-quality checks, and baseline reconciliation always describe the full snapshot. Zero-match selections show an empty state and no average order value. Tables scroll within keyboard-focusable containers on narrow screens.

Total order amount includes all selected statuses and payment methods, including coupons, gift cards, and returned orders. Completed-order amount includes only completed orders. No refunds are inferred.

## Reproduce validation

From the project root using the existing Wren environment:

```powershell
& ../.venv/Scripts/python.exe apps/jaffle-shop-analytics/validate_snapshot.py
& ../.venv/Scripts/wren.exe genbi verify jaffle-shop-analytics
```

The export script only writes within this app. It queries through Wren, checks all executive KPIs, reconciles monthly amount to AUD 1,672 and monthly order count to 99, and asserts zero issues for all three quality checks. It does not rebuild or modify the semantic layer.

`browser_checks.py` uses Playwright installed under the temporary `jaffle-browser-tools` directory and installed Chrome. With the local server running, it tests the browser KPIs, 30 filter combinations, empty selections, reset, keyboard behavior, disclosures, tooltips, console errors, and document overflow at 320, 375, 768, 1024, and 1440 pixels. Screenshots are written to the temporary `jaffle-browser-checks` directory.

GenBI's verification includes its built-in secret scan. The dashboard contains no credentials or warehouse connection configuration. No deployment is configured or performed.
