#!/usr/bin/env python3
"""
GhidulReducerilor.ro — Motor de Scraping
Scanează toate magazinele partenere și extrage reducerile active.

Utilizare:
  python scripts/scraper.py --mode full
  python scripts/scraper.py --mode flash
  python scripts/scraper.py --magazine emag
"""

import json
import os
import sys
import time
import hashlib
import logging
import argparse
import requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

# Configurare logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('logs/scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('scraper')

# Căi
ROOT = Path(__file__).parent.parent
CONFIG_DIR = ROOT / 'config'
DATA_DIR = ROOT / 'data'
RAW_DIR = DATA_DIR / 'raw'
PROCESSED_DIR = DATA_DIR / 'processed'
LOGS_DIR = ROOT / 'logs'

# Asigurăm că directoarele există
for d in [RAW_DIR, PROCESSED_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    """Încarcă configurația magazinelor."""
    with open(CONFIG_DIR / 'magazines.json', 'r', encoding='utf-8') as f:
        return json.load(f)


def load_existing_deals() -> list:
    """Încarcă ofertele existente din deals.json."""
    deals_path = DATA_DIR / 'deals.json'
    if deals_path.exists():
        with open(deals_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def generate_deal_id(magazin: str, url: str) -> str:
    """Generează un ID unic pentru o ofertă."""
    return f"{magazin}-{hashlib.md5(url.encode()).hexdigest()[:8]}"


def calculate_real_discount(pret_nou: float, pret_vechi: float) -> float:
    """Calculează reducerea reală în procente."""
    if pret_vechi <= 0 or pret_nou >= pret_vechi:
        return 0
    return round(((pret_vechi - pret_nou) / pret_vechi) * 100, 1)


def calculate_deal_score(deal: dict) -> float:
    """
    Calculează scorul de valoare al unei oferte (1-10).
    Scor bazat pe: reducere reală, stoc, rating, popularitate.
    """
    score = 5.0

    discount = deal.get('discount_percent', 0)
    if discount >= 50:
        score += 2.0
    elif discount >= 30:
        score += 1.5
    elif discount >= 20:
        score += 1.0
    elif discount >= 15:
        score += 0.5

    if deal.get('in_stock', True):
        score += 0.5

    rating = deal.get('rating', 0)
    if rating >= 4.5:
        score += 1.0
    elif rating >= 4.0:
        score += 0.5

    if deal.get('price_history_verified', False):
        score += 1.0

    if deal.get('is_fake_discount', False):
        score -= 3.0

    return min(max(round(score, 1), 1.0), 10.0)


def validate_omnibus(deal: dict, pret_minim_30z: Optional[float]) -> dict:
    """
    Validare conform Directivei Omnibus UE.
    Afișăm prețul minim din ultimele 30 de zile.
    """
    deal['omnibus_validated'] = False

    if pret_minim_30z is None:
        deal['pret_minim_30z'] = deal.get('original_price')
        return deal

    deal['pret_minim_30z'] = pret_minim_30z

    if deal.get('original_price', 0) < pret_minim_30z:
        deal['is_fake_discount'] = True
        logger.warning(f"Reducere falsă detectată: {deal.get('title')} — prețul vechi e mai mic decât minimul din 30 zile")
    else:
        deal['omnibus_validated'] = True

    return deal


def scrape_emag_rss() -> list:
    """
    Scrape oferte eMAG via RSS/API.
    În producție: folosește API-ul Profitshare pentru feed de produse.
    """
    logger.info("Scraping eMAG...")
    deals = []

    # TODO: Înlocuiește cu apel real API Profitshare
    # GET https://api.profitshare.ro/products/feed?affiliate_id=ZN4M&magazine=emag
    try:
        headers = {'User-Agent': 'GhidulReducerilor/1.0 (https://ghidulreducerilor.ro)'}
        # Simulare pentru demonstrație — în producție apelezi API real
        logger.info("eMAG: folosind date existente din deals.json")
        return []
    except Exception as e:
        logger.error(f"Eroare scraping eMAG: {e}")
        return []


def scrape_fashiondays_rss() -> list:
    """Scrape oferte FashionDays via Profitshare."""
    logger.info("Scraping FashionDays...")
    try:
        # TODO: API Profitshare feed pentru FashionDays
        return []
    except Exception as e:
        logger.error(f"Eroare scraping FashionDays: {e}")
        return []


def scrape_magazine_html(magazine_key: str, config: dict) -> list:
    """
    Scrape generic HTML pentru magazine fără API.
    Folosește sitemap și pagini de promotii.
    """
    mag_config = config['magazines'].get(magazine_key)
    if not mag_config:
        logger.error(f"Config inexistent pentru magazin: {magazine_key}")
        return []

    logger.info(f"Scraping {mag_config['name']} (HTML)...")
    deals = []

    try:
        promotii_url = mag_config.get('fallback_url', mag_config['url'] + '/promotii')
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; GhidulReducerilor/1.0)',
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'ro-RO,ro;q=0.9'
        }

        response = requests.get(promotii_url, headers=headers, timeout=15)
        response.raise_for_status()

        # TODO: Parsare HTML cu BeautifulSoup
        # soup = BeautifulSoup(response.content, 'html.parser')
        # products = soup.find_all('div', class_='product-card')
        # for product in products:
        #     deal = extract_deal_from_html(product, magazine_key, mag_config)
        #     if deal:
        #         deals.append(deal)

        logger.info(f"{mag_config['name']}: {len(deals)} oferte găsite")

    except requests.RequestException as e:
        logger.error(f"Eroare HTTP pentru {magazine_key}: {e}")
    except Exception as e:
        logger.error(f"Eroare scraping {magazine_key}: {e}")

    return deals


def run_full_scrape(config: dict) -> list:
    """Rulează scraping complet pe toate magazinele active."""
    all_deals = []

    for mag_key, mag_config in config['magazines'].items():
        if mag_config.get('status') in ['activ', 'pending_approval']:
            try:
                if mag_config.get('affiliate_network') == 'profitshare':
                    if mag_key == 'emag':
                        deals = scrape_emag_rss()
                    elif mag_key == 'fashiondays':
                        deals = scrape_fashiondays_rss()
                    else:
                        deals = scrape_magazine_html(mag_key, config)
                else:
                    deals = scrape_magazine_html(mag_key, config)

                # Procesare deals
                for deal in deals:
                    deal['magazine_key'] = mag_key
                    deal['magazine_name'] = mag_config['name']
                    deal['scraped_at'] = datetime.now(timezone.utc).isoformat()
                    deal['score'] = calculate_deal_score(deal)

                    # Filtrare după scor minim
                    min_score = config.get('setari_globale', {}).get('scor_minim_publicare', 5)
                    if deal['score'] >= min_score:
                        all_deals.append(deal)

                logger.info(f"{mag_config['name']}: {len(deals)} oferte procesate")

            except Exception as e:
                logger.error(f"Eroare la {mag_key}: {e}")

    logger.info(f"Total oferte noi: {len(all_deals)}")
    return all_deals


def run_flash_scrape(config: dict) -> list:
    """Scraping rapid pentru flash sales (magazinele principale)."""
    logger.info("Flash scrape — magazine principale")
    flash_magazines = ['emag', 'fashiondays', 'notino', 'answear']
    all_deals = []

    for mag_key in flash_magazines:
        if mag_key in config['magazines']:
            deals = scrape_magazine_html(mag_key, config)
            all_deals.extend(deals)

    return all_deals


def save_raw_data(deals: list, mode: str) -> str:
    """Salvează date brute cu timestamp."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = RAW_DIR / f"scrape_{mode}_{timestamp}.json"

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(deals, f, ensure_ascii=False, indent=2)

    logger.info(f"Date brute salvate: {filename}")
    return str(filename)


def main():
    parser = argparse.ArgumentParser(description='GhidulReducerilor Scraper')
    parser.add_argument('--mode', choices=['full', 'flash', 'evening'], default='full')
    parser.add_argument('--magazine', help='Scrape doar un magazin specific')
    parser.add_argument('--dry-run', action='store_true', help='Nu salvează date')
    args = parser.parse_args()

    logger.info(f"=== Scraper pornit — mod: {args.mode} ===")
    start_time = time.time()

    config = load_config()

    if args.magazine:
        deals = scrape_magazine_html(args.magazine, config)
    elif args.mode == 'full':
        deals = run_full_scrape(config)
    elif args.mode in ['flash', 'evening']:
        deals = run_flash_scrape(config)
    else:
        deals = run_full_scrape(config)

    if not args.dry_run and deals:
        save_raw_data(deals, args.mode)

    elapsed = round(time.time() - start_time, 2)
    logger.info(f"=== Scraping finalizat în {elapsed}s — {len(deals)} oferte ===")

    return deals


if __name__ == '__main__':
    main()
