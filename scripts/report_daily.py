#!/usr/bin/env python3
"""
GhidulReducerilor.ro — Generator Raport Zilnic
Generează statistici, KPI și alertă pe email/log.

Utilizare:
  python scripts/report_daily.py
  python scripts/report_daily.py --date 2026-03-29
  python scripts/report_daily.py --send-email
"""

import json
import os
import sys
import logging
import argparse
import glob as glob_module
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import Counter

try:
    import requests
except ImportError:
    print("Instalează requests: pip install requests")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('logs/report.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('report')

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / 'data'
LOGS_DIR = ROOT / 'logs'

sys.path.insert(0, str(Path(__file__).parent))
from utils import normalize_deal  # noqa: E402

BREVO_API_KEY = os.environ.get('BREVO_API_KEY', '')
BREVO_API_URL = 'https://api.brevo.com/v3'
REPORT_EMAIL = os.environ.get('REPORT_EMAIL', 'hello@ghidulreducerilor.ro')


def load_deals() -> list:
    """Încarcă ofertele din deals.json (normalizate EN+RO)."""
    deals_path = DATA_DIR / 'deals.json'
    if deals_path.exists():
        with open(deals_path, 'r', encoding='utf-8') as f:
            return [normalize_deal(d) for d in json.load(f)]
    return []


def load_pipeline_stats(date_str: str) -> dict:
    """Încarcă statisticile pipeline-ului pentru o dată."""
    stats_path = LOGS_DIR / f"pipeline_stats_{date_str.replace('-', '')}.json"
    if stats_path.exists():
        with open(stats_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def load_link_check_stats(date_str: str) -> dict:
    """Încarcă statisticile de verificare linkuri."""
    pattern = str(LOGS_DIR / f"link_check_{date_str.replace('-', '')}*.json")
    files = sorted(glob_module.glob(pattern))
    if files:
        with open(files[-1], 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def analyze_deals(deals: list, date_str: str) -> dict:
    """Analizează ofertele și generează statistici."""
    now = datetime.now(timezone.utc)
    today = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
    tomorrow = today + timedelta(days=1)

    active_deals = [d for d in deals if d.get('is_active', True)]
    total_deals = len(deals)

    # Deals adăugate azi
    deals_today = []
    for d in deals:
        scraped = d.get('scraped_at', '')
        if scraped:
            try:
                scraped_dt = datetime.fromisoformat(scraped.replace('Z', '+00:00'))
                if today <= scraped_dt < tomorrow:
                    deals_today.append(d)
            except (ValueError, AttributeError):
                pass

    # Distribuție pe magazine
    stores = Counter(d.get('store', d.get('magazine_name', 'Unknown')) for d in active_deals)

    # Distribuție pe discount
    discounts = [d.get('discount_percent', 0) for d in active_deals if d.get('discount_percent', 0) > 0]
    avg_discount = round(sum(discounts) / len(discounts), 1) if discounts else 0
    max_discount = max(discounts) if discounts else 0

    # Deals cu score înalt (>=7)
    high_score_deals = [d for d in active_deals if d.get('score', 0) >= 7]

    # Deals cu linkuri moarte
    broken_links = [d for d in deals if d.get('link_status') in ['not_found', 'server_error']]

    # Top 5 deals după scor
    top_deals = sorted(active_deals, key=lambda d: (
        d.get('score', 5),
        d.get('discount_percent', 0)
    ), reverse=True)[:5]

    return {
        'total_deals': total_deals,
        'active_deals': len(active_deals),
        'deals_adaugate_azi': len(deals_today),
        'avg_discount': avg_discount,
        'max_discount': max_discount,
        'high_score_deals': len(high_score_deals),
        'broken_links': len(broken_links),
        'top_magazine': stores.most_common(1)[0] if stores else ('N/A', 0),
        'distributie_magazine': dict(stores.most_common(10)),
        'top_5_deals': [
            {
                'title': d.get('title', '')[:50],
                'discount': d.get('discount_percent', 0),
                'score': d.get('score', 0),
                'store': d.get('store', d.get('magazine_name', ''))
            }
            for d in top_deals
        ]
    }


def get_brevo_campaign_stats(date_str: str) -> dict:
    """Obține statistici campanie email din Brevo."""
    if not BREVO_API_KEY:
        return {'status': 'no_api_key'}

    headers = {
        'api-key': BREVO_API_KEY,
        'Content-Type': 'application/json'
    }

    try:
        response = requests.get(
            f'{BREVO_API_URL}/emailCampaigns',
            headers=headers,
            params={'status': 'sent', 'limit': 5},
            timeout=15
        )

        if response.status_code == 200:
            campaigns = response.json().get('campaigns', [])
            # Filtrează campaniile de azi
            today_campaigns = []
            for camp in campaigns:
                sent_date = camp.get('sentDate', '')
                if sent_date and date_str in sent_date:
                    today_campaigns.append({
                        'name': camp.get('name', ''),
                        'subject': camp.get('subject', ''),
                        'sent_count': camp.get('statistics', {}).get('globalStats', {}).get('sent', 0),
                        'open_rate': camp.get('statistics', {}).get('globalStats', {}).get('uniqueOpens', 0),
                        'click_rate': camp.get('statistics', {}).get('globalStats', {}).get('uniqueClicks', 0),
                        'unsubscribes': camp.get('statistics', {}).get('globalStats', {}).get('unsubscriptions', 0)
                    })

            return {'campaigns': today_campaigns, 'status': 'ok'}

    except Exception as e:
        logger.error(f"Eroare Brevo stats: {e}")

    return {'status': 'error'}


def calculate_kpi_status(deals_stats: dict, email_stats: dict) -> dict:
    """Calculează statusul KPI față de target-uri."""
    kpi = {}

    # Deals KPI
    kpi['deals_active'] = {
        'valoare': deals_stats.get('active_deals', 0),
        'target': 50,
        'status': 'ok' if deals_stats.get('active_deals', 0) >= 50 else 'warning'
    }

    kpi['deals_noi_azi'] = {
        'valoare': deals_stats.get('deals_adaugate_azi', 0),
        'target': 10,
        'status': 'ok' if deals_stats.get('deals_adaugate_azi', 0) >= 10 else 'warning'
    }

    kpi['discount_mediu'] = {
        'valoare': deals_stats.get('avg_discount', 0),
        'target': 25,
        'status': 'ok' if deals_stats.get('avg_discount', 0) >= 25 else 'info'
    }

    kpi['linkuri_moarte'] = {
        'valoare': deals_stats.get('broken_links', 0),
        'target': 0,
        'status': 'ok' if deals_stats.get('broken_links', 0) == 0 else 'error'
    }

    # Email KPI (dacă avem date)
    campaigns = email_stats.get('campaigns', [])
    if campaigns:
        camp = campaigns[0]
        sent = camp.get('sent_count', 1)
        if sent > 0:
            open_rate = round(camp.get('open_rate', 0) / sent * 100, 1)
            click_rate = round(camp.get('click_rate', 0) / sent * 100, 1)

            kpi['email_open_rate'] = {
                'valoare': open_rate,
                'target': 25,
                'status': 'ok' if open_rate >= 25 else 'warning'
            }

            kpi['email_ctr'] = {
                'valoare': click_rate,
                'target': 4,
                'status': 'ok' if click_rate >= 4 else 'warning'
            }

    return kpi


def generate_html_report(date_str: str, deals_stats: dict, pipeline_stats: dict,
                          link_stats: dict, email_stats: dict, kpi: dict) -> str:
    """Generează raport HTML."""

    kpi_rows = ''
    for key, data in kpi.items():
        icon = '✅' if data['status'] == 'ok' else '⚠️' if data['status'] == 'warning' else '❌' if data['status'] == 'error' else 'ℹ️'
        kpi_rows += f"""
        <tr>
            <td style="padding:8px;border-bottom:1px solid #eee;">{key}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;text-align:center;font-weight:600;">{data['valoare']}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;text-align:center;color:#999;">{data['target']}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;text-align:center;">{icon}</td>
        </tr>"""

    top_deals_rows = ''
    for deal in deals_stats.get('top_5_deals', []):
        top_deals_rows += f"""
        <tr>
            <td style="padding:6px;border-bottom:1px solid #f5f5f5;">{deal['title']}</td>
            <td style="padding:6px;border-bottom:1px solid #f5f5f5;text-align:center;">-{deal['discount']}%</td>
            <td style="padding:6px;border-bottom:1px solid #f5f5f5;text-align:center;">{deal['score']}</td>
            <td style="padding:6px;border-bottom:1px solid #f5f5f5;">{deal['store']}</td>
        </tr>"""

    magazine_rows = ''
    for store, count in deals_stats.get('distributie_magazine', {}).items():
        magazine_rows += f"""
        <tr>
            <td style="padding:6px;border-bottom:1px solid #f5f5f5;">{store}</td>
            <td style="padding:6px;border-bottom:1px solid #f5f5f5;text-align:center;font-weight:600;">{count}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Raport Zilnic {date_str} — GhidulReducerilor.ro</title>
</head>
<body style="font-family:-apple-system,sans-serif;background:#f8f8f8;margin:0;padding:20px;">
<table width="700" cellpadding="0" cellspacing="0" style="background:white;border-radius:12px;padding:30px;margin:0 auto;">

<tr><td>
<h1 style="color:#e53e3e;margin:0 0 5px;">📊 Raport Zilnic</h1>
<p style="color:#999;margin:0 0 30px;">{date_str} | GhidulReducerilor.ro</p>
</td></tr>

<!-- Stats overview -->
<tr><td>
<table width="100%" cellpadding="10">
<tr>
    <td style="background:#f0fff4;border-radius:8px;text-align:center;width:25%;">
        <div style="font-size:28px;font-weight:700;color:#38a169;">{deals_stats.get('active_deals', 0)}</div>
        <div style="color:#666;font-size:12px;">Deals Active</div>
    </td>
    <td width="10"></td>
    <td style="background:#fff5f5;border-radius:8px;text-align:center;width:25%;">
        <div style="font-size:28px;font-weight:700;color:#e53e3e;">{deals_stats.get('deals_adaugate_azi', 0)}</div>
        <div style="color:#666;font-size:12px;">Noi Azi</div>
    </td>
    <td width="10"></td>
    <td style="background:#ebf8ff;border-radius:8px;text-align:center;width:25%;">
        <div style="font-size:28px;font-weight:700;color:#3182ce;">{deals_stats.get('avg_discount', 0)}%</div>
        <div style="color:#666;font-size:12px;">Reducere Medie</div>
    </td>
    <td width="10"></td>
    <td style="background:#fffff0;border-radius:8px;text-align:center;width:25%;">
        <div style="font-size:28px;font-weight:700;color:#d69e2e;">{deals_stats.get('high_score_deals', 0)}</div>
        <div style="color:#666;font-size:12px;">Score ≥7</div>
    </td>
</tr>
</table>
</td></tr>

<tr><td style="padding:20px 0 10px;"><h2 style="margin:0;font-size:16px;">📋 KPI Status</h2></td></tr>
<tr><td>
<table width="100%" style="border:1px solid #eee;border-radius:8px;">
<tr style="background:#f8f8f8;">
    <th style="padding:8px;text-align:left;">Metric</th>
    <th style="padding:8px;">Valoare</th>
    <th style="padding:8px;">Target</th>
    <th style="padding:8px;">Status</th>
</tr>
{kpi_rows}
</table>
</td></tr>

<tr><td style="padding:20px 0 10px;"><h2 style="margin:0;font-size:16px;">🏆 Top 5 Deals Azi</h2></td></tr>
<tr><td>
<table width="100%" style="border:1px solid #eee;border-radius:8px;">
<tr style="background:#f8f8f8;">
    <th style="padding:8px;text-align:left;">Produs</th>
    <th style="padding:8px;">Reducere</th>
    <th style="padding:8px;">Score</th>
    <th style="padding:8px;text-align:left;">Magazin</th>
</tr>
{top_deals_rows}
</table>
</td></tr>

<tr><td style="padding:20px 0 10px;"><h2 style="margin:0;font-size:16px;">🏪 Distribuție Magazine</h2></td></tr>
<tr><td>
<table width="100%" style="border:1px solid #eee;border-radius:8px;">
<tr style="background:#f8f8f8;">
    <th style="padding:8px;text-align:left;">Magazin</th>
    <th style="padding:8px;">Nr. Deals</th>
</tr>
{magazine_rows}
</table>
</td></tr>

<tr><td style="padding:30px 0 0;border-top:1px solid #eee;margin-top:20px;">
<p style="color:#bbb;font-size:11px;text-align:center;margin:0;">
    Generat automat de GhidulReducerilor.ro · {datetime.now().strftime('%d.%m.%Y %H:%M')}
</p>
</td></tr>

</table>
</body>
</html>"""


def send_report_email(html: str, date_str: str) -> bool:
    """Trimite raportul pe email via Brevo."""
    if not BREVO_API_KEY:
        logger.warning("BREVO_API_KEY lipsește — raport netrimit pe email")
        return False

    headers = {
        'api-key': BREVO_API_KEY,
        'Content-Type': 'application/json'
    }

    email_data = {
        "sender": {"name": "GhidulReducerilor Bot", "email": "hello@ghidulreducerilor.ro"},
        "to": [{"email": REPORT_EMAIL}],
        "subject": f"📊 Raport zilnic {date_str} — GhidulReducerilor.ro",
        "htmlContent": html
    }

    try:
        response = requests.post(
            f'{BREVO_API_URL}/smtp/email',
            headers=headers,
            json=email_data,
            timeout=30
        )

        if response.status_code == 201:
            logger.info(f"Raport trimis pe email: {REPORT_EMAIL}")
            return True
        else:
            logger.error(f"Eroare trimitere raport: {response.status_code} — {response.text[:200]}")
            return False

    except Exception as e:
        logger.error(f"Eroare la trimitere raport email: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='GhidulReducerilor Daily Report')
    parser.add_argument('--date', default=datetime.now().strftime('%Y-%m-%d'))
    parser.add_argument('--send-email', action='store_true', help='Trimite raport pe email')
    parser.add_argument('--output', help='Salvează HTML în fișier')
    args = parser.parse_args()

    logger.info(f"=== Raport Zilnic: {args.date} ===")

    deals = load_deals()
    pipeline_stats = load_pipeline_stats(args.date)
    link_stats = load_link_check_stats(args.date)
    email_stats = get_brevo_campaign_stats(args.date)

    deals_stats = analyze_deals(deals, args.date)
    kpi = calculate_kpi_status(deals_stats, email_stats)

    # Generează HTML
    html = generate_html_report(
        args.date, deals_stats, pipeline_stats,
        link_stats, email_stats, kpi
    )

    # Salvează raport
    report_path = LOGS_DIR / f"daily_report_{args.date.replace('-', '')}.html"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html)
    logger.info(f"Raport HTML salvat: {report_path}")

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(html)

    if args.send_email:
        send_report_email(html, args.date)

    # Print sumar în consolă
    print(f"\n=== RAPORT ZILNIC {args.date} ===")
    print(f"Deals active: {deals_stats['active_deals']}")
    print(f"Deals noi azi: {deals_stats['deals_adaugate_azi']}")
    print(f"Reducere medie: {deals_stats['avg_discount']}%")
    print(f"Reducere max: {deals_stats['max_discount']}%")
    print(f"Linkuri moarte: {deals_stats['broken_links']}")

    print(f"\nKPI Status:")
    for metric, data in kpi.items():
        icon = '✅' if data['status'] == 'ok' else '⚠️' if data['status'] == 'warning' else '❌'
        print(f"  {icon} {metric}: {data['valoare']} (target: {data['target']})")

    print(f"\nRaport salvat: {report_path}")


if __name__ == '__main__':
    main()
