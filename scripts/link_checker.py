#!/usr/bin/env python3
"""
GhidulReducerilor.ro — Verificator Linkuri Afiliate
Verifică sănătatea linkurilor: redirect corect, produs disponibil, preț actual.

Utilizare:
  python scripts/link_checker.py --mode full
  python scripts/link_checker.py --mode quick
  python scripts/link_checker.py --deal-id emag-abc12345
"""

import json
import os
import sys
import time
import logging
import argparse
import concurrent.futures
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError:
    print("Instalează requests: pip install requests")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('logs/link_checker.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('link_checker')

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / 'data'
LOGS_DIR = ROOT / 'logs'

sys.path.insert(0, str(Path(__file__).parent))
from utils import normalize_deal  # noqa: E402

# Timeout și retry settings
REQUEST_TIMEOUT = 15
MAX_WORKERS = 10
RETRY_COUNT = 2


def create_session() -> requests.Session:
    """Creează sesiune requests cu retry logic."""
    session = requests.Session()
    retry_strategy = Retry(
        total=RETRY_COUNT,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (compatible; GhidulReducerilor-LinkChecker/1.0)',
        'Accept': 'text/html,application/xhtml+xml,*/*',
        'Accept-Language': 'ro-RO,ro;q=0.9,en;q=0.8'
    })
    return session


def load_deals() -> list:
    """Încarcă ofertele din deals.json (normalizate EN+RO)."""
    deals_path = DATA_DIR / 'deals.json'
    if deals_path.exists():
        with open(deals_path, 'r', encoding='utf-8') as f:
            return [normalize_deal(d) for d in json.load(f)]
    return []


def save_deals(deals: list):
    """Salvează deals.json actualizat."""
    deals_path = DATA_DIR / 'deals.json'
    with open(deals_path, 'w', encoding='utf-8') as f:
        json.dump(deals, f, ensure_ascii=False, indent=2)


def check_link(session: requests.Session, deal: dict) -> dict:
    """
    Verifică un singur link afiliat.
    Returnează status, final_url, status_code, response_time.
    """
    link = deal.get('affiliate_url') or deal.get('url', '')
    deal_id = deal.get('id', 'unknown')
    result = {
        'id': deal_id,
        'url': link,
        'status': 'unknown',
        'status_code': None,
        'final_url': None,
        'response_time_ms': None,
        'is_product_page': False,
        'checked_at': datetime.now(timezone.utc).isoformat(),
        'error': None
    }

    if not link or link == '#':
        result['status'] = 'no_url'
        return result

    start_time = time.time()

    try:
        response = session.get(
            link,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True
        )

        elapsed_ms = round((time.time() - start_time) * 1000)
        result['response_time_ms'] = elapsed_ms
        result['status_code'] = response.status_code
        result['final_url'] = response.url

        if response.status_code == 200:
            result['status'] = 'ok'
            # Verifică dacă e pagina produsului (URL final conține cuvinte cheie produse)
            final_url_lower = response.url.lower()
            product_indicators = ['product', 'p/', '/produs/', 'item', 'pd/', 'detail']
            result['is_product_page'] = any(ind in final_url_lower for ind in product_indicators)

        elif response.status_code == 404:
            result['status'] = 'not_found'
        elif response.status_code == 403:
            result['status'] = 'forbidden'
        elif response.status_code >= 500:
            result['status'] = 'server_error'
        elif response.status_code in [301, 302, 308]:
            result['status'] = 'redirect'
        else:
            result['status'] = f'http_{response.status_code}'

        logger.debug(f"[{result['status']}] {deal_id}: {link} ({elapsed_ms}ms)")

    except requests.exceptions.Timeout:
        result['status'] = 'timeout'
        result['error'] = 'Request timeout'
    except requests.exceptions.ConnectionError as e:
        result['status'] = 'connection_error'
        result['error'] = str(e)[:100]
    except requests.exceptions.TooManyRedirects:
        result['status'] = 'too_many_redirects'
        result['error'] = 'Too many redirects'
    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)[:100]

    return result


def check_profitshare_link(link: str) -> bool:
    """
    Verifică dacă un link Profitshare (/out/ID) este valid.
    Linkurile l.profitshare.ro directe sunt blocate pe mobile — folosim /out/[id].
    """
    if '/out/' not in link and 'l.profitshare.ro' in link:
        logger.warning(f"Link Profitshare direct detectat (blocat pe mobile): {link}")
        return False
    return True


def check_2performant_link(link: str, deal_id: str) -> dict:
    """Verifică dacă un link 2Performant este valid și activ."""
    result = {'valid': True, 'warning': None}

    if '2performant.com' in link or 'evt.4ps.ro' in link:
        # Verificăm că linkul conține codul afiliat
        if 'aff_id=' not in link and 'affiliate_id=' not in link:
            result['warning'] = 'Link 2Performant fără ID afiliat'

    return result


def update_deal_link_status(deal: dict, check_result: dict) -> dict:
    """Actualizează statusul link-ului în obiectul deal."""
    deal['link_status'] = check_result['status']
    deal['link_checked_at'] = check_result['checked_at']

    if check_result['status'] in ['not_found', 'server_error', 'connection_error']:
        # Marchează deal ca inactiv dacă link-ul nu mai funcționează (EN + RO sync)
        deal['is_active'] = False
        deal['activ'] = False  # sync frontend
        logger.warning(f"Deal marcat inactiv (link mort): {deal.get('id')} — {check_result['status']}")

    if check_result['status'] == 'timeout':
        # Nu dezactivăm la timeout, poate fi temporar
        deal['link_timeout_count'] = deal.get('link_timeout_count', 0) + 1
        if deal.get('link_timeout_count', 0) >= 3:
            deal['is_active'] = False
            deal['activ'] = False  # sync frontend
            logger.warning(f"Deal dezactivat după 3 timeout-uri: {deal.get('id')}")

    return deal


def run_checks(deals: list, mode: str = 'full', deal_id: Optional[str] = None) -> dict:
    """
    Rulează verificările de linkuri.
    mode: 'full' — toate, 'quick' — doar deals active, 'single' — un deal specific
    """
    if deal_id:
        deals_to_check = [d for d in deals if d.get('id') == deal_id]
    elif mode == 'quick':
        # Quick: doar deals active fără verificare recentă
        deals_to_check = [
            d for d in deals
            if d.get('is_active', True)
            and not d.get('link_checked_at')  # Niciodată verificate
        ][:50]  # Max 50 pentru quick
    else:
        # Full: toate deals active
        deals_to_check = [d for d in deals if d.get('is_active', True)]

    logger.info(f"Verificare {len(deals_to_check)} linkuri (mod: {mode})")

    if not deals_to_check:
        logger.info("Nu există linkuri de verificat")
        return {'total': 0, 'ok': 0, 'broken': 0, 'errors': []}

    session = create_session()
    results = []
    broken_deals = []
    ok_count = 0

    # Verificare paralelă
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_deal = {
            executor.submit(check_link, session, deal): deal
            for deal in deals_to_check
        }

        for future in concurrent.futures.as_completed(future_to_deal):
            deal = future_to_deal[future]
            try:
                result = future.result()
                results.append(result)

                if result['status'] == 'ok':
                    ok_count += 1
                elif result['status'] in ['not_found', 'server_error', 'connection_error', 'too_many_redirects']:
                    broken_deals.append({
                        'id': deal.get('id'),
                        'title': deal.get('title', ''),
                        'url': result['url'],
                        'status': result['status']
                    })
                    logger.warning(f"Link mort: {deal.get('id')} [{result['status']}]")

            except Exception as e:
                logger.error(f"Eroare la verificare {deal.get('id')}: {e}")

    # Actualizează deals cu rezultatele
    results_by_id = {r['id']: r for r in results}
    updated_count = 0

    for i, deal in enumerate(deals):
        if deal.get('id') in results_by_id:
            deals[i] = update_deal_link_status(deal, results_by_id[deal['id']])

            # Verificare link Profitshare
            link = deal.get('affiliate_url', '')
            if not check_profitshare_link(link):
                deals[i]['link_warning'] = 'profitshare_direct_blocked_mobile'

            updated_count += 1

    stats = {
        'total_checked': len(deals_to_check),
        'ok': ok_count,
        'broken': len(broken_deals),
        'broken_deals': broken_deals,
        'updated_deals': updated_count,
        'checked_at': datetime.now(timezone.utc).isoformat()
    }

    logger.info(f"Verificare completă: {ok_count} OK, {len(broken_deals)} broken din {len(deals_to_check)}")

    return stats, deals


def save_report(stats: dict):
    """Salvează raportul de verificare."""
    report_path = LOGS_DIR / f"link_check_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    logger.info(f"Raport salvat: {report_path}")


def main():
    parser = argparse.ArgumentParser(description='GhidulReducerilor Link Checker')
    parser.add_argument('--mode', choices=['full', 'quick'], default='quick')
    parser.add_argument('--deal-id', help='Verifică doar un deal specific')
    parser.add_argument('--dry-run', action='store_true', help='Verifică dar nu salvează modificări')
    args = parser.parse_args()

    logger.info(f"=== Link Checker — mod: {args.mode} ===")

    deals = load_deals()

    result = run_checks(deals, mode=args.mode, deal_id=args.deal_id)

    if isinstance(result, tuple):
        stats, updated_deals = result
    else:
        stats = result
        updated_deals = deals

    save_report(stats)

    if not args.dry_run:
        save_deals(updated_deals)
        logger.info(f"Deals actualizate cu statusul link-urilor")

    # Raport sumar
    print(f"\n=== RAPORT LINK CHECKER ===")
    print(f"Total verificate: {stats.get('total_checked', 0)}")
    print(f"✅ OK: {stats.get('ok', 0)}")
    print(f"❌ Broken: {stats.get('broken', 0)}")

    if stats.get('broken_deals'):
        print(f"\nLinkuri moarte:")
        for broken in stats['broken_deals'][:10]:
            print(f"  - {broken['id']}: {broken['status']} ({broken['url'][:60]})")

    return stats


if __name__ == '__main__':
    main()
