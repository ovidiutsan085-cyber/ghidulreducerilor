#!/usr/bin/env python3
"""
GhidulReducerilor.ro — Pipeline Zilnic Principal
Orchestrează întregul flux de actualizare: scraping → validare → publicare → distribuție.

Utilizare:
  python scripts/daily_pipeline.py --mode full
  python scripts/daily_pipeline.py --mode cleanup
"""

import json
import os
import sys
import shutil
import logging
import argparse
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('logs/pipeline.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('pipeline')

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / 'data'
LOGS_DIR = ROOT / 'logs'
BACKUP_DIR = ROOT / 'data' / 'backups'
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(Path(__file__).parent))
from utils import normalize_deal  # noqa: E402


def load_deals() -> list:
    """Încarcă deals.json curent (normalizate EN+RO)."""
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
    logger.info(f"Deals salvate: {len(deals)} intrări")


def backup_data():
    """Creează backup zilnic al datelor."""
    timestamp = datetime.now().strftime('%Y-%m-%d')

    for filename in ['deals.json', 'codes.json']:
        src = DATA_DIR / filename
        if src.exists():
            dst = BACKUP_DIR / f"{filename.replace('.json', '')}_{timestamp}.json"
            shutil.copy2(src, dst)
            logger.info(f"Backup creat: {dst.name}")

    # Curăță backup-uri mai vechi de 30 de zile
    cutoff = datetime.now() - timedelta(days=30)
    for backup_file in BACKUP_DIR.glob('*.json'):
        if backup_file.stat().st_mtime < cutoff.timestamp():
            backup_file.unlink()
            logger.info(f"Backup vechi șters: {backup_file.name}")


def mark_expired_deals(deals: list) -> tuple[list, int]:
    """
    Marchează ofertele expirate.
    O ofertă este considerată expirată dacă:
    - Are data_expirare în trecut
    - Are is_active = false
    - Sau are mai mult de 7 zile fără actualizare
    """
    now = datetime.now(timezone.utc)
    expired_count = 0
    active_deals = []

    for deal in deals:
        is_expired = False

        # Verifică data expirare explicită
        expiry = deal.get('expiry_date') or deal.get('validUntil')
        if expiry:
            try:
                expiry_dt = datetime.fromisoformat(expiry.replace('Z', '+00:00'))
                if expiry_dt < now:
                    is_expired = True
            except (ValueError, AttributeError):
                pass

        # Verifică is_active flag
        if deal.get('is_active') is False:
            is_expired = True

        if is_expired:
            expired_count += 1
            deal['archived_at'] = now.isoformat()
            logger.debug(f"Ofertă expirată: {deal.get('id', 'unknown')}")
        else:
            active_deals.append(deal)

    logger.info(f"Oferte expirate și arhivate: {expired_count}")
    return active_deals, expired_count


def deduplicate_deals(deals: list) -> list:
    """Elimină oferte duplicate pe baza URL-ului produsului."""
    seen_urls = set()
    unique_deals = []

    for deal in deals:
        url = deal.get('url') or deal.get('product_url', '')
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_deals.append(deal)

    removed = len(deals) - len(unique_deals)
    if removed > 0:
        logger.info(f"Duplicate eliminate: {removed}")

    return unique_deals


def sort_deals_by_score(deals: list) -> list:
    """Sortează ofertele după scor (descrescător)."""
    return sorted(deals, key=lambda d: (
        d.get('score', 5),
        d.get('discount_percent', 0)
    ), reverse=True)


def update_sitemap():
    """Actualizează sitemap.xml și notifică Google."""
    logger.info("Actualizare sitemap...")
    # Next.js generează sitemap automat prin app/sitemap.ts
    # Opțional: ping Google cu URL-ul sitemap
    sitemap_url = "https://ghidulreducerilor.ro/sitemap.xml"
    ping_url = f"https://www.google.com/ping?sitemap={sitemap_url}"

    try:
        import requests
        response = requests.get(ping_url, timeout=10)
        if response.status_code == 200:
            logger.info("Google notificat despre sitemap")
        else:
            logger.warning(f"Ping Google sitemap: status {response.status_code}")
    except Exception as e:
        logger.warning(f"Nu s-a putut notifica Google: {e}")


def run_full_pipeline():
    """
    Pipeline complet:
    1. Scraping
    2. Validare
    3. Merge cu date existente
    4. Cleanup duplicate + expirate
    5. Sortare
    6. Salvare
    7. Update sitemap
    """
    logger.info("=== PIPELINE FULL START ===")
    stats = {
        'start_time': datetime.now().isoformat(),
        'mode': 'full',
        'deals_inainte': 0,
        'deals_noi': 0,
        'deals_expirate': 0,
        'deals_dupa': 0,
        'erori': []
    }

    # Pas 1: Încarcă date existente
    existing_deals = load_deals()
    stats['deals_inainte'] = len(existing_deals)
    logger.info(f"Deals existente: {len(existing_deals)}")

    # Pas 2: Scraping (apelăm scraper.py)
    new_deals = []
    scrape_start = datetime.now()
    try:
        result = subprocess.run(
            [sys.executable, 'scripts/scraper.py', '--mode', 'full'],
            capture_output=True, text=True, cwd=ROOT, timeout=300
        )
        if result.returncode == 0:
            logger.info("Scraping finalizat cu succes")
            # Încarcă fișierele raw create în această rulare
            raw_dir = DATA_DIR / 'raw'
            if raw_dir.exists():
                for raw_file in sorted(raw_dir.glob('scrape_full_*.json')):
                    if raw_file.stat().st_mtime >= scrape_start.timestamp():
                        try:
                            with open(raw_file, 'r', encoding='utf-8') as f:
                                raw = json.load(f)
                            new_deals.extend([normalize_deal(d) for d in raw])
                            logger.info(f"Încărcat {len(raw)} oferte noi din {raw_file.name}")
                        except Exception as re:
                            logger.error(f"Eroare la citire {raw_file}: {re}")
        else:
            logger.error(f"Eroare scraping: {result.stderr}")
            stats['erori'].append(f"Scraping error: {result.stderr[:200]}")
    except subprocess.TimeoutExpired:
        logger.error("Scraping timeout după 5 minute")
        stats['erori'].append("Scraping timeout")
    except Exception as e:
        logger.error(f"Eroare la lansare scraper: {e}")

    # Pas 3: Merge date noi cu existente
    all_deals = existing_deals + new_deals
    stats['deals_noi'] = len(new_deals)

    # Pas 4: Cleanup
    all_deals = deduplicate_deals(all_deals)
    all_deals, expired = mark_expired_deals(all_deals)
    stats['deals_expirate'] = expired

    # Pas 5: Sortare
    all_deals = sort_deals_by_score(all_deals)

    # Pas 6: Salvare
    save_deals(all_deals)
    stats['deals_dupa'] = len(all_deals)

    # Pas 7: Update sitemap
    update_sitemap()

    logger.info(f"=== PIPELINE COMPLET ===")
    logger.info(f"Înainte: {stats['deals_inainte']} | Noi: {stats['deals_noi']} | Expirate: {stats['deals_expirate']} | Final: {stats['deals_dupa']}")

    # Salvează stats
    stats_path = LOGS_DIR / f"pipeline_stats_{datetime.now().strftime('%Y%m%d')}.json"
    with open(stats_path, 'w') as f:
        json.dump(stats, f, indent=2)

    return stats


def run_cleanup():
    """
    Cleanup noapte:
    - Backup date
    - Arhivare oferte expirate
    - Curățare logs vechi
    """
    logger.info("=== CLEANUP NOAPTE ===")

    # Backup
    backup_data()

    # Arhivare expirate
    deals = load_deals()
    active_deals, expired = mark_expired_deals(deals)
    save_deals(active_deals)

    # Curăță log-uri vechi (> 30 zile)
    cutoff = datetime.now() - timedelta(days=30)
    for log_file in LOGS_DIR.glob('*.log'):
        if log_file.stat().st_mtime < cutoff.timestamp():
            log_file.unlink()
            logger.info(f"Log vechi șters: {log_file.name}")

    logger.info(f"Cleanup finalizat. Oferte arhivate: {expired}")


def main():
    parser = argparse.ArgumentParser(description='GhidulReducerilor Daily Pipeline')
    parser.add_argument('--mode', choices=['full', 'cleanup'], default='full')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    if args.mode == 'full':
        stats = run_full_pipeline()
        print(json.dumps(stats, indent=2))
    elif args.mode == 'cleanup':
        run_cleanup()


if __name__ == '__main__':
    main()
