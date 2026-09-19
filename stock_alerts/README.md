# Stock Alerts (optional add-on)

Checks your live Shopify inventory once a week and tells you — by email
and a desktop notification — if anything has hit 0 stock. This is
separate from the rest of the project on purpose: everything else here
reads a static CSV someone downloaded by hand, so it can be verified and
dated. This add-on instead calls Shopify's real Admin API every time it
runs, so what it reports is only ever "as of right now" — see
`check_stock.py`'s header comment for the full reasoning.

## What you need before this works

1. A Shopify Admin API access token (read-only is enough).
2. An email account you're willing to send alerts from.

Both are real credentials — they go in a `.env` file in this folder
that's already excluded from git (see the root `.gitignore`), never in
code, never committed.

## 1. Get a Shopify Admin API token

1. In your Shopify admin: **Settings → Apps and sales channels → Develop
   apps** (you may need to click "Allow custom app development" once,
   the first time).
2. **Create an app** — name it something like `Seamark Stock Alerts`.
3. **Configuration → Admin API integration → Configure**: under
   "Admin API access scopes", tick **read_products** and
   **read_inventory**. Save.
4. **Install app** (top right). Confirm.
5. Go to the **API credentials** tab and copy the **Admin API access
   token** — it starts with `shpat_` and is shown only once. If you
   lose it, revoke it from this same screen and generate a new one;
   nothing else needs to change.
6. Your store domain is the `your-store.myshopify.com` address (not
   your custom domain, if you have one) — you can see it in your
   Shopify admin URL.

## 2. Get an email app password (example: Gmail)

Gmail (and most providers) won't accept your normal account password
for a script like this. For Gmail:

1. Turn on **2-Step Verification** on your Google account if it isn't
   already (myaccount.google.com/security).
2. Go to myaccount.google.com/apppasswords, create one named something
   like `Seamark Stock Alerts`, and copy the 16-character password it
   gives you.

Using a different provider (Outlook, Yahoo, a work email)? The same
idea applies — look for "app password" in that provider's account
security settings, and set `SMTP_SERVER` / `SMTP_PORT` in `.env` to
that provider's SMTP settings instead of Gmail's.

## 3. Set up this folder

```
cd stock_alerts
pip install -r requirements.txt
copy .env.example .env
```

Open `.env` and fill in the six real values from steps 1 and 2 above.

## 4. Test it manually before scheduling anything

```
python check_stock.py
```

This should print how many products are in stock, out of stock, and
not tracked, save `outputs/stock_check.csv`, and send you a test email
+ desktop notification either way (a clean run says so explicitly, so
you know it actually ran rather than silently doing nothing). Fix
whatever it complains about before moving on — a scheduled task that
fails silently every week is worse than no automation at all.

## 5. Schedule it to run weekly (Windows Task Scheduler)

Once the manual test above works, register it to run automatically.
Open PowerShell and run (adjust the day/time if you'd rather it run at
a different point in the week):

```
schtasks /create /tn "Seamark Weekly Stock Check" /tr "C:\Users\sunny\OneDrive\Desktop\Seamark_DataScience_Project2\stock_alerts\weekly_check.bat" /sc weekly /d MON /st 09:00
```

This only needs to be run once — Windows will remember it. A few notes:

- **`python` must resolve for Task Scheduler, not just your terminal.**
  Task Scheduler doesn't always use the same PATH as an interactive
  PowerShell window — if the weekly run doesn't seem to happen, run
  `where python` in PowerShell, then edit `weekly_check.bat` to call
  that full path instead of the bare word `python`.
- Every run appends to `stock_alerts/weekly_check.log` in this folder —
  check that file first if something seems off.
- By default, Task Scheduler only runs while you're logged in and your
  computer is on. In Task Scheduler's own app (search "Task Scheduler"
  in Windows), you can find "Seamark Weekly Stock Check" under Task
  Scheduler Library and tick "Run whether user is logged on or not" or
  "Wake the computer to run this task" if you want it more reliable —
  neither is required to get started.
- To change the schedule later: `schtasks /change /tn "Seamark Weekly Stock Check" /st 08:00` (for example). To remove it entirely:
  `schtasks /delete /tn "Seamark Weekly Stock Check"`.

## What `outputs/stock_check.csv` contains

One row per product: `Handle`, `Title`, `Auto_Category`,
`live_inventory_qty`, `stock_status` (`in stock` / `out of stock` /
`not tracked`), and `checked_at_utc` — the exact time of the last run
that actually pulled from Shopify. The dashboard's Stock Alerts section
reads this same file, so it's only ever as fresh as your last run —
there's no live polling inside the dashboard itself.

## Why some products say "not tracked"

If a product's variant has Shopify inventory tracking turned off,
Shopify itself isn't enforcing a stock count for it — it can be sold
regardless of quantity. This script reports that honestly as "not
tracked" rather than guessing whether it's "in stock" or "out of
stock", the same rule the rest of this project follows for any number
it doesn't actually have.
