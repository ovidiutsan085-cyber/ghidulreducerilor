#!/usr/bin/env python3
"""
GhidulReducerilor.ro — Generator și Trimițător Newsletter
Generează newsletter zilnic/săptămânal și îl trimite via Brevo API.

Utilizare:
  python scripts/newsletter.py --type daily
  python scripts/newsletter.py --type weekly
  python scripts/newsletter.py --type price_alert --product-id notino-001
"""

import json
import os
import sys
import logging
import argparse
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    print("Instalează requests: pip install requests")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('logs/newsletter.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('newsletter')

ROOT = Path(__file__).parent.parent
CONFIG_DIR = ROOT / 'config'
DATA_DIR = ROOT / 'data'

sys.path.insert(0, str(Path(__file__).parent))
from utils import normalize_deal  # noqa: E402

# Brevo API
BREVO_API_KEY = os.environ.get('BREVO_API_KEY', '')
BREVO_API_URL = 'https://api.brevo.com/v3'
BREVO_LIST_ID = int(os.environ.get('BREVO_LIST_ID', '2'))


def load_deals() -> list:
    """Încarcă ofertele active (normalizate EN+RO)."""
    with open(DATA_DIR / 'deals.json', 'r', encoding='utf-8') as f:
        return [normalize_deal(d) for d in json.load(f)]


def load_codes() -> list:
    """Încarcă codurile promoționale active."""
    with open(DATA_DIR / 'codes.json', 'r', encoding='utf-8') as f:
        return json.load(f)


def load_templates() -> dict:
    """Încarcă template-urile de email."""
    with open(CONFIG_DIR / 'email_templates.json', 'r', encoding='utf-8') as f:
        return json.load(f)


def get_top_deals(deals: list, n: int = 10) -> list:
    """Returnează cele mai bune n oferte după scor."""
    active = [d for d in deals if d.get('is_active', True)]
    sorted_deals = sorted(active, key=lambda d: (
        d.get('score', 5),
        d.get('discount_percent', 0)
    ), reverse=True)
    return sorted_deals[:n]


def get_active_codes(codes: list, n: int = 3) -> list:
    """Returnează cele mai relevante coduri active."""
    now = datetime.now(timezone.utc)
    active = []
    for code in codes:
        if code.get('active', True):
            expiry = code.get('validUntil', '')
            if expiry:
                try:
                    exp_dt = datetime.fromisoformat(expiry.replace('Z', '+00:00'))
                    if exp_dt > now:
                        active.append(code)
                except (ValueError, AttributeError):
                    active.append(code)
            else:
                active.append(code)
    return active[:n]


def generate_deal_html(deal: dict) -> str:
    """Generează HTML pentru un deal în newsletter."""
    title = deal.get('title', 'Produs în reducere')
    discount = deal.get('discount_percent', 0)
    store = deal.get('store', deal.get('magazine_name', ''))
    price_new = deal.get('price', deal.get('newPrice', 0))
    price_old = deal.get('originalPrice', deal.get('original_price', 0))
    link = deal.get('affiliate_url') or deal.get('url', '#')
    image = deal.get('image', '')

    price_str = f"{price_new} RON" if price_new else ""
    old_price_str = f"<s style='color:#999'>{price_old} RON</s> → " if price_old else ""

    return f"""
    <tr>
      <td style="padding:12px;border-bottom:1px solid #f0f0f0;">
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td width="80" style="padding-right:12px;vertical-align:top;">
              {'<img src="' + image + '" width="80" style="border-radius:8px;" alt="">' if image else '<div style="width:80px;height:80px;background:#f5f5f5;border-radius:8px;"></div>'}
            </td>
            <td style="vertical-align:top;">
              <p style="margin:0 0 4px;font-weight:600;color:#1a1a1a;font-size:14px;">{title}</p>
              <p style="margin:0 0 4px;color:#666;font-size:12px;">🏪 {store}</p>
              <p style="margin:0 0 8px;font-size:14px;">{old_price_str}<strong style="color:#e53e3e;">{price_str}</strong></p>
              <a href="{link}" style="background:#e53e3e;color:white;padding:6px 16px;border-radius:20px;text-decoration:none;font-size:12px;font-weight:600;">
                -{discount}% → Cumpără acum
              </a>
            </td>
          </tr>
        </table>
      </td>
    </tr>
    """


def generate_code_html(code: dict) -> str:
    """Generează HTML pentru un cod promoțional."""
    store = code.get('store', '')
    cod = code.get('code', '')
    discount = code.get('discount', '')
    link = code.get('affiliate_url') or code.get('url', '#')

    return f"""
    <tr>
      <td style="padding:8px;border:2px dashed #e53e3e;border-radius:8px;margin-bottom:8px;text-align:center;">
        <p style="margin:0;font-size:12px;color:#666;">🏪 {store}</p>
        <p style="margin:4px 0;font-size:20px;font-weight:900;letter-spacing:3px;color:#e53e3e;font-family:monospace;">{cod}</p>
        <p style="margin:0;font-size:12px;color:#333;">{discount}</p>
        <a href="{link}" style="color:#e53e3e;font-size:11px;text-decoration:underline;">Folosește codul →</a>
      </td>
    </tr>
    """


def generate_newsletter_html(deals: list, codes: list, newsletter_type: str = 'daily') -> str:
    """Generează HTML complet pentru newsletter."""
    now = datetime.now()
    data_ro = now.strftime('%-d %B %Y').replace(
        'January', 'Ianuarie').replace('February', 'Februarie').replace(
        'March', 'Martie').replace('April', 'Aprilie').replace(
        'May', 'Mai').replace('June', 'Iunie').replace(
        'July', 'Iulie').replace('August', 'August').replace(
        'September', 'Septembrie').replace('October', 'Octombrie').replace(
        'November', 'Noiembrie').replace('December', 'Decembrie')

    top_deals = get_top_deals(deals, 10)
    top_codes = get_active_codes(codes, 3)

    max_discount = max([d.get('discount_percent', 0) for d in top_deals], default=0)

    deals_html = ''.join([generate_deal_html(d) for d in top_deals])
    codes_html = ''.join([generate_code_html(c) for c in top_codes]) if top_codes else ''

    codes_section = f"""
    <tr>
      <td style="padding:20px 0 10px;font-size:18px;font-weight:700;color:#1a1a1a;">
        🎟️ Coduri Promoționale Active
      </td>
    </tr>
    <table width="100%" cellpadding="8" cellspacing="4">
      {codes_html}
    </table>
    """ if codes_html else ''

    return f"""
<!DOCTYPE html>
<html lang="ro">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Top Reduceri {data_ro} | GhidulReducerilor.ro</title>
</head>
<body style="margin:0;padding:0;background:#f8f8f8;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8f8f8;">
    <tr>
      <td align="center" style="padding:20px;">
        <table width="600" cellpadding="0" cellspacing="0" style="background:white;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">

          <!-- Header -->
          <tr>
            <td style="background:linear-gradient(135deg,#e53e3e 0%,#c53030 100%);padding:30px;text-align:center;">
              <h1 style="margin:0;color:white;font-size:28px;font-weight:800;">🛍️ GhidulReducerilor.ro</h1>
              <p style="margin:8px 0 0;color:rgba(255,255,255,0.9);font-size:14px;">
                Top {len(top_deals)} Reduceri · {data_ro} · Până la -{max_discount}%
              </p>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:24px;">
              <p style="margin:0 0 16px;color:#555;font-size:14px;">
                Bună! 👋 Iată cele mai bune reduceri verificate de azi:
              </p>

              <!-- Deals -->
              <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #f0f0f0;border-radius:8px;overflow:hidden;">
                {deals_html}
              </table>

              <!-- Coduri -->
              {codes_section}

              <!-- CTA -->
              <tr>
                <td style="padding:24px 0;text-align:center;">
                  <a href="https://ghidulreducerilor.ro" style="background:#e53e3e;color:white;padding:14px 32px;border-radius:25px;text-decoration:none;font-size:16px;font-weight:700;display:inline-block;">
                    🔍 Vezi Toate Reducerile →
                  </a>
                </td>
              </tr>

            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background:#f8f8f8;padding:20px;text-align:center;border-top:1px solid #eee;">
              <p style="margin:0 0 8px;color:#999;font-size:12px;">
                © {now.year} GhidulReducerilor.ro · Reduceri verificate din România
              </p>
              <p style="margin:0;font-size:11px;color:#bbb;">
                <a href="{{{{ unsubscribe }}}}" style="color:#bbb;">Dezabonare</a> ·
                <a href="https://ghidulreducerilor.ro" style="color:#bbb;">Site</a>
              </p>
              <p style="margin:8px 0 0;font-size:10px;color:#ccc;">
                Link-urile conțin coduri de afiliere. Prețurile pot varia.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def send_newsletter_brevo(subject: str, html_content: str, list_id: int) -> bool:
    """Trimite newsletter via Brevo API."""
    if not BREVO_API_KEY:
        logger.error("BREVO_API_KEY nu este setat!")
        return False

    headers = {
        'api-key': BREVO_API_KEY,
        'Content-Type': 'application/json'
    }

    # Creează campanie
    campaign_data = {
        "name": f"Newsletter {datetime.now().strftime('%d-%m-%Y')}",
        "subject": subject,
        "sender": {"name": "GhidulReducerilor.ro", "email": "hello@ghidulreducerilor.ro"},
        "type": "classic",
        "htmlContent": html_content,
        "recipients": {"listIds": [list_id]},
        "scheduledAt": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    }

    try:
        # Creează campania
        response = requests.post(
            f'{BREVO_API_URL}/emailCampaigns',
            headers=headers,
            json=campaign_data,
            timeout=30
        )

        if response.status_code == 201:
            campaign_id = response.json().get('id')
            logger.info(f"Campanie creată: ID {campaign_id}")

            # Trimite campania
            send_response = requests.post(
                f'{BREVO_API_URL}/emailCampaigns/{campaign_id}/sendNow',
                headers=headers,
                timeout=30
            )

            if send_response.status_code == 204:
                logger.info(f"Newsletter trimis cu succes! Campanie: {campaign_id}")
                return True
            else:
                logger.error(f"Eroare trimitere newsletter: {send_response.status_code} — {send_response.text}")
                return False
        else:
            logger.error(f"Eroare creare campanie: {response.status_code} — {response.text}")
            return False

    except requests.RequestException as e:
        logger.error(f"Eroare conexiune Brevo: {e}")
        return False


def generate_subject(newsletter_type: str, deals: list, templates: dict) -> str:
    """Generează subject line optimizat pentru newsletter."""
    top_deals = get_top_deals(deals, 10)
    max_discount = max([d.get('discount_percent', 0) for d in top_deals], default=0)
    now = datetime.now()

    subject_templates = templates.get('templates', {}).get(
        f'newsletter_{newsletter_type}', {}).get('subject_templates', [
        f"🛍️ Top reduceri {now.strftime('%d.%m.%Y')} — până la -{max_discount}%"
    ])

    # Alege random un template
    template = random.choice(subject_templates)

    # Substituie variabile
    zile = ['Luni', 'Marți', 'Miercuri', 'Joi', 'Vineri', 'Sâmbătă', 'Duminică']
    return template.replace('{numar}', str(len(top_deals))) \
                   .replace('{procent_max}', str(max_discount)) \
                   .replace('{data}', now.strftime('%d.%m.%Y')) \
                   .replace('{zi_saptamana}', zile[now.weekday()])


def main():
    parser = argparse.ArgumentParser(description='GhidulReducerilor Newsletter')
    parser.add_argument('--type', choices=['daily', 'weekly', 'price_alert'], default='daily')
    parser.add_argument('--product-id', help='ID produs pentru alerta de preț')
    parser.add_argument('--dry-run', action='store_true', help='Generează dar nu trimite')
    parser.add_argument('--output', help='Salvează HTML în fișier')
    args = parser.parse_args()

    logger.info(f"=== Newsletter {args.type} ===")

    deals = load_deals()
    codes = load_codes()
    templates = load_templates()

    html = generate_newsletter_html(deals, codes, args.type)
    subject = generate_subject(args.type, deals, templates)

    logger.info(f"Subject: {subject}")
    logger.info(f"Deals incluse: {len(get_top_deals(deals, 10))}")

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(html)
        logger.info(f"HTML salvat: {args.output}")

    if not args.dry_run:
        success = send_newsletter_brevo(subject, html, BREVO_LIST_ID)
        if success:
            logger.info("✅ Newsletter trimis cu succes!")
        else:
            logger.error("❌ Eroare la trimitere newsletter")
            sys.exit(1)
    else:
        logger.info("DRY RUN — Newsletter netrimit")
        print(f"\nSubject: {subject}")
        print(f"Lungime HTML: {len(html)} caractere")


if __name__ == '__main__':
    main()
