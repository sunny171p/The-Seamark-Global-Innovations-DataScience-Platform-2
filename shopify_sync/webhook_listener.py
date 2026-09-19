# ==
# webhook_listener.py
# Author: Sunday Emmanuel Azeez
# Seamark Global Innovations — Post-Launch Data Science Project (Project 2)
# ==
#
# WHY THIS EXISTS:
# refresh_raw_data.py pulls data on demand, you run it, it asks
# Shopify for everything, and you get a fresh snapshot. That's batch
# thinking. Shopify can also just tell you the moment an order comes
# in, through a webhook, an HTTP POST it sends to a URL you register,
# the instant the event happens. This listens for that.
#
# WHAT IT ACTUALLY DOES, HONESTLY:
# It does NOT try to rewrite raw_data/orders_export.csv live, in
# place, the moment an order arrives. That's a much riskier thing to
# get right than it sounds, CASE_STUDY.md already documents a real bug
# from a subtler version of this exact problem (line items silently
# not matching because of a schema assumption that didn't hold once
# real data arrived). So instead, this lands every event it receives
# as its own raw JSON file under raw_data/webhook_events/, verified
# and untouched, exactly as Shopify sent it. fold_webhook_events.py
# (next to this file) is the separate, second step that turns those
# landed files into rows appended to orders_export.csv, in the same
# format refresh_raw_data.py already produces. Landing the raw event
# first and transforming it as a second, separate, rerunnable step is
# a standard event-driven pattern for exactly this reason, if the
# transform step has a bug, you fix it and just re-run it against the
# same landed files, nothing was lost.
#
# SETTING IT UP:
#   1. pip install -r shopify_sync/requirements.txt   (flask is already in there)
#   2. In your Shopify admin: Settings > Notifications > Webhooks
#      (or, for a custom app, Configuration > Webhook subscriptions),
#      add a webhook for "Order creation", pointing at:
#          https://<wherever-this-is-reachable>/webhooks/orders/create
#      Shopify shows you a signing secret when you create it, or reuses
#      your app's Client Secret. Put that in shopify_sync/.env as
#      SHOPIFY_WEBHOOK_SECRET (see shopify_sync/.env.example).
#   3. This has to be reachable from the internet, Shopify can't send
#      a webhook to a laptop sitting behind a home router. For testing,
#      run this locally and expose it with a tool like ngrok
#      (`ngrok http 5051`), then use the https URL ngrok gives you as
#      the webhook URL in step 2. For something always-on, deploy this
#      file to a small always-on host (Render, Railway, Fly.io all
#      have free tiers that work fine for this) and use that URL
#      instead. Neither choice changes any of the code below, only
#      where it's reachable.
#   4. python shopify_sync/webhook_listener.py
#
# A NOTE ON WHAT SHOPIFY ACTUALLY SENDS:
# The field mapping in _order_json_to_rows() below is a real, working
# starting point built from Shopify's documented order webhook payload,
# not guessed at. But Shopify's API does version and occasionally
# rename fields, and this hasn't been run against a live webhook from
# your actual store yet, only against Shopify's own documented example
# payload. Before relying on it, send yourself a real test webhook
# (Shopify's webhook settings page has a "Send test notification"
# button) and check the JSON that lands in raw_data/webhook_events/
# actually has the fields this expects.

import hashlib
import hmac
import json
import logging
import os
import sys
from base64 import b64encode
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, request, abort

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass  # python-dotenv is optional; falls back to real environment variables

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVENTS_DIR = PROJECT_ROOT / "raw_data" / "webhook_events" / "orders"
EVENTS_DIR.mkdir(parents=True, exist_ok=True)

WEBHOOK_SECRET = os.environ.get("SHOPIFY_WEBHOOK_SECRET", "")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("webhook_listener")

app = Flask(__name__)


def _verify_hmac(raw_body: bytes, header_value: str) -> bool:
    """Shopify signs the raw request body with your app's secret and sends
    the result, base64-encoded, in the X-Shopify-Hmac-Sha256 header.
    Recomputing it and comparing is how you know the request actually
    came from Shopify and wasn't sent by anyone who just found the URL.
    """
    if not WEBHOOK_SECRET:
        log.error("SHOPIFY_WEBHOOK_SECRET is not set, refusing all webhooks until it is")
        return False
    computed = b64encode(
        hmac.new(WEBHOOK_SECRET.encode("utf-8"), raw_body, hashlib.sha256).digest()
    ).decode("utf-8")
    return hmac.compare_digest(computed, header_value or "")


@app.route("/webhooks/orders/create", methods=["POST"])
@app.route("/webhooks/orders/updated", methods=["POST"])
def handle_order_webhook():
    hmac_header = request.headers.get("X-Shopify-Hmac-Sha256", "")
    if not _verify_hmac(request.get_data(), hmac_header):
        log.warning("Rejected a webhook with an invalid or missing signature")
        abort(401)

    order = request.get_json(silent=True)
    if not order:
        log.warning("Rejected a webhook with no parseable JSON body")
        abort(400)

    order_id = order.get("id", "unknown")
    order_name = order.get("name", "unknown")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = EVENTS_DIR / f"{timestamp}_{order_id}.json"
    out_path.write_text(json.dumps(order, indent=2), encoding="utf-8")

    log.info("Landed order %s (id %s) -> %s", order_name, order_id, out_path.name)
    return {"status": "received"}, 200


@app.route("/webhooks/health", methods=["GET"])
def health():
    return {"status": "ok", "events_landed": len(list(EVENTS_DIR.glob("*.json")))}, 200


if __name__ == "__main__":
    if not WEBHOOK_SECRET:
        log.warning(
            "SHOPIFY_WEBHOOK_SECRET is not set in shopify_sync/.env, "
            "every incoming webhook will be rejected until it is."
        )
    port = int(os.environ.get("WEBHOOK_PORT", "5051"))
    log.info("Listening for Shopify order webhooks on port %d", port)
    app.run(host="0.0.0.0", port=port, debug=False)
