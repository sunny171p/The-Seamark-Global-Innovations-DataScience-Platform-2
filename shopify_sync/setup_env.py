# ==
# setup_env.py
# Author: Sunday Emmanuel Azeez
# Seamark Global Innovations — Shopify Sync add-on
# ==
#
# WHY THIS EXISTS:
# Typing SHOPIFY_STORE_DOMAIN=... directly into PowerShell fails, because
# PowerShell tries to run it as a program name, not save it to a file.
# Building the .env file by hand (heredocs, Add-Content lines) has been
# error-prone too. This script sidesteps all of that: it just asks a
# question at a time, and writes shopify_sync/.env for you. Nothing you
# type here is sent anywhere except into that local file.
#
# HOW TO RUN IT:
#   cd shopify_sync
#   python setup_env.py
#
# Then answer each question and press Enter. Leave a question blank
# (just press Enter) if it doesn't apply to you — see the two options
# explained when you run it.
# ==

from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent / ".env"


def ask(prompt: str) -> str:
    return input(prompt).strip()


def main() -> None:
    print("=" * 62)
    print("  Shopify Sync — .env setup")
    print("=" * 62)
    print()
    print("This will create shopify_sync/.env for you. Answer each")
    print("question below, then press Enter. Nothing you type here")
    print("leaves this computer.")
    print()

    domain = ask("1. Your store domain (example: jde08t-zs.myshopify.com): ")

    print()
    print("2. Does your Shopify custom app's credentials page show a")
    print("   permanent token starting with shpat_, OR a Client ID")
    print("   plus a Secret starting with shpss_?")
    print()
    kind = ""
    while kind not in ("a", "b"):
        kind = ask("   Type 'a' for shpat_ token, or 'b' for Client ID + Secret: ").lower()

    token = ""
    client_id = ""
    client_secret = ""

    if kind == "a":
        print()
        token = ask("3. Paste your shpat_ Admin API access token: ")
    else:
        print()
        client_id = ask("3. Paste your Client ID: ")
        print()
        client_secret = ask("4. Paste your Client Secret (starts with shpss_): ")

    lines = [f"SHOPIFY_STORE_DOMAIN={domain}"]
    if token:
        lines.append(f"SHOPIFY_ADMIN_API_ACCESS_TOKEN={token}")
    if client_id:
        lines.append(f"SHOPIFY_CLIENT_ID={client_id}")
    if client_secret:
        lines.append(f"SHOPIFY_CLIENT_SECRET={client_secret}")
    lines.append("SHOPIFY_API_VERSION=2026-07")

    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print()
    print("=" * 62)
    print(f"  Done. Wrote {ENV_PATH}")
    print("  Next: python refresh_raw_data.py")
    print("=" * 62)


if __name__ == "__main__":
    main()
