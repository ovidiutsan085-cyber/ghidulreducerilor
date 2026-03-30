#!/usr/bin/env python3
"""
GhidulReducerilor.ro — Creator Campanii Sezoniere
Generează campanii speciale: Black Friday, Paște, Crăciun, Back-to-School, etc.

Utilizare:
  python scripts/campaign_creator.py --season black_friday
  python scripts/campaign_creator.py --season paste
  python scripts/campaign_creator.py --list
"""

import json
import os
import logging
import argparse
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('logs/campaign.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('campaign')

import sys

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / 'data'
CONFIG_DIR = ROOT / 'config'

sys.path.insert(0, str(Path(__file__).parent))
from utils import normalize_deal  # noqa: E402

# Definiții campanii sezoniere
CAMPAIGNS = {
    'black_friday': {
        'name': 'Black Friday',
        'emoji': '🖤',
        'culoare': '#1a1a1a',
        'luni': [11],  # Noiembrie
        'zile_inainte_teaser': 14,
        'discount_minim': 30,
        'categorii_principale': ['electronice', 'IT', 'fashion', 'casa'],
        'hashtags': ['#BlackFriday', '#BlackFridayRomania', '#reduceriBlackFriday', '#BF2026'],
        'subject_templates': [
            '🖤 Black Friday {an}: până la -{procent}% la {magazin}!',
            '⏰ {zile} zile până la Black Friday — primele oferte live!',
            '🔥 BLACK FRIDAY {an} — Ofertele pe care le așteptai!'
        ],
        'fb_template': '🖤 BLACK FRIDAY {an} LIVE!\n\n💥 Reduceri de până la -{procent}% la {magazin}\n\n🛍️ Toate ofertele verificate pe:\n👉 ghidulreducerilor.ro/black-friday\n\n#BlackFriday #Reduceri #GhidulReducerilor'
    },
    'paste': {
        'name': 'Paște',
        'emoji': '🐣',
        'culoare': '#68d391',
        'luni': [3, 4],  # Martie-Aprilie
        'zile_inainte_teaser': 7,
        'discount_minim': 20,
        'categorii_principale': ['casa', 'fashion', 'beauty', 'carti'],
        'hashtags': ['#Paste', '#PasteRomania', '#reduceriPaste', '#ofertePaste'],
        'subject_templates': [
            '🐣 Oferte de Paște — -{procent}% la {magazin}',
            '🌸 Reduceri de primăvară + Paște | GhidulReducerilor',
            '🎁 Cadouri de Paște în reducere — Top {numar} oferte'
        ],
        'fb_template': '🐣 REDUCERI DE PAȘTE!\n\n🌸 Cele mai bune oferte pentru sărbători:\n{lista_deals}\n\n🛍️ Toate pe ghidulreducerilor.ro\n\n#Paste #Reduceri #GhidulReducerilor'
    },
    'craciun': {
        'name': 'Crăciun',
        'emoji': '🎄',
        'culoare': '#e53e3e',
        'luni': [12],
        'zile_inainte_teaser': 30,
        'discount_minim': 20,
        'categorii_principale': ['electronice', 'IT', 'jucarii', 'fashion', 'casa'],
        'hashtags': ['#Craciun', '#CraciunRomania', '#CadouriCraciun', '#reduceriCraciun'],
        'subject_templates': [
            '🎄 Reduceri de Crăciun — Top cadouri la -{procent}%',
            '🎁 {numar} idei de cadouri în reducere | Crăciun {an}',
            '⛄ Oferte Crăciun {an} — -{procent}% la {magazin}'
        ],
        'fb_template': '🎄 REDUCERI DE CRĂCIUN {an}!\n\n🎁 Cele mai bune cadouri la prețuri reduse:\n{lista_deals}\n\n🛍️ Toate pe ghidulreducerilor.ro\n\n#Craciun #Cadouri #GhidulReducerilor'
    },
    'back_to_school': {
        'name': 'Back to School',
        'emoji': '🎒',
        'culoare': '#4299e1',
        'luni': [8, 9],  # August-Septembrie
        'zile_inainte_teaser': 14,
        'discount_minim': 15,
        'categorii_principale': ['IT', 'electronice', 'rechizite', 'fashion'],
        'hashtags': ['#BackToSchool', '#RentreeScolaire', '#rechizite', '#laptop', '#scoala'],
        'subject_templates': [
            '🎒 Back to School — Laptop-uri și rechizite la -{procent}%',
            '📚 {numar} oferte pentru școală | GhidulReducerilor',
            '✏️ Pregătit pentru școală? Reduceri de până la -{procent}%!'
        ],
        'fb_template': '🎒 BACK TO SCHOOL {an}!\n\n📚 Reduceri la rechizite, laptopuri și accesorii:\n{lista_deals}\n\n🛍️ ghidulreducerilor.ro\n\n#BackToSchool #Reduceri'
    },
    'vara': {
        'name': 'Vară',
        'emoji': '☀️',
        'culoare': '#f6ad55',
        'luni': [6, 7, 8],
        'zile_inainte_teaser': 7,
        'discount_minim': 20,
        'categorii_principale': ['fashion', 'sport', 'electronice', 'casa'],
        'hashtags': ['#Vara', '#VaraRomania', '#reduceriVara', '#summer', '#ofertevara'],
        'subject_templates': [
            '☀️ Reduceri de vară — -{procent}% la {magazin}',
            '🏖️ Pregătit de vacanță? Oferte de până la -{procent}%',
            '🌞 Top {numar} reduceri ale sezonului de vară'
        ],
        'fb_template': '☀️ REDUCERI DE VARĂ!\n\n🏖️ Tot ce ai nevoie pentru vacanță la prețuri reduse:\n{lista_deals}\n\n🛍️ ghidulreducerilor.ro\n\n#Vara #Reduceri #GhidulReducerilor'
    },
    '1_martie': {
        'name': '1 Martie — Mărțișor',
        'emoji': '🌸',
        'culoare': '#ed64a6',
        'luni': [3],
        'zile_inainte_teaser': 5,
        'discount_minim': 15,
        'categorii_principale': ['beauty', 'cosmetice', 'fashion', 'bijuterii'],
        'hashtags': ['#1Martie', '#Martisoare', '#Martisor', '#reduceri1Martie'],
        'subject_templates': [
            '🌸 1 Martie — Cadouri frumoase în reducere!',
            '💐 Oferte speciale de Mărțișor | GhidulReducerilor',
            '🎀 Top {numar} cadouri de 1 Martie la -{procent}%'
        ],
        'fb_template': '🌸 1 MARTIE — OFERTE SPECIALE!\n\n💐 Cadouri frumoase pentru cei dragi, la prețuri reduse:\n{lista_deals}\n\n🛍️ ghidulreducerilor.ro\n\n#1Martie #Martisor #GhidulReducerilor'
    },
    '8_martie': {
        'name': '8 Martie — Ziua Femeii',
        'emoji': '💐',
        'culoare': '#e879f9',
        'luni': [3],
        'zile_inainte_teaser': 7,
        'discount_minim': 15,
        'categorii_principale': ['beauty', 'cosmetice', 'fashion', 'bijuterii', 'parfum'],
        'hashtags': ['#8Martie', '#ZiuaFemeii', '#WomensDay', '#reduceri8Martie'],
        'subject_templates': [
            '💐 8 Martie — Reduceri la cosmetice și fashion',
            '🌹 Ziua Femeii: -{procent}% la parfumuri și beauty',
            '💝 Top {numar} cadouri de 8 Martie | GhidulReducerilor'
        ],
        'fb_template': '💐 8 MARTIE — ZIUA FEMEII!\n\n🌹 Reduceri speciale la cosmetice, parfumuri și fashion:\n{lista_deals}\n\n🛍️ ghidulreducerilor.ro\n\n#8Martie #ZiuaFemeii #GhidulReducerilor'
    }
}


def get_current_season() -> str:
    """Detectează sezonul curent pe baza lunii și zilei."""
    now = datetime.now()
    month = now.month
    day = now.day

    # Verificări specifice
    if month == 3 and day <= 2:
        return '1_martie'
    if month == 3 and 6 <= day <= 9:
        return '8_martie'
    if month == 11:
        return 'black_friday'
    if month == 12:
        return 'craciun'
    if month in [3, 4]:
        return 'paste'
    if month in [8, 9]:
        return 'back_to_school'
    if month in [6, 7]:
        return 'vara'

    return None


def get_upcoming_campaign(days_ahead: int = 30) -> dict:
    """Returnează campania care urmează în următoarele N zile."""
    now = datetime.now()

    # Definim datele fixe importante din an
    upcoming = []
    year = now.year

    fixed_dates = {
        '1_martie': datetime(year, 3, 1),
        '8_martie': datetime(year, 3, 8),
        'paste': datetime(year, 4, 20),  # Aproximativ — variază
        'back_to_school': datetime(year, 9, 1),
        'black_friday': datetime(year, 11, 28),  # Ultima vineri noiembrie
        'craciun': datetime(year, 12, 25),
        'vara': datetime(year, 6, 1),
    }

    for campaign_key, campaign_date in fixed_dates.items():
        if campaign_date > now:
            days_until = (campaign_date - now).days
            if days_until <= days_ahead:
                upcoming.append({
                    'key': campaign_key,
                    'days_until': days_until,
                    'date': campaign_date.strftime('%d.%m.%Y'),
                    'config': CAMPAIGNS[campaign_key]
                })

    if upcoming:
        return min(upcoming, key=lambda x: x['days_until'])
    return None


def load_deals_for_campaign(season: str) -> list:
    """Încarcă deal-urile relevante pentru campanie (normalizate EN+RO)."""
    deals_path = DATA_DIR / 'deals.json'
    if not deals_path.exists():
        return []

    with open(deals_path, 'r', encoding='utf-8') as f:
        all_deals = [normalize_deal(d) for d in json.load(f)]

    campaign = CAMPAIGNS.get(season)
    if not campaign:
        return all_deals

    target_categories = campaign.get('categorii_principale', [])
    min_discount = campaign.get('discount_minim', 15)

    # Filtrare
    relevant = []
    for deal in all_deals:
        if not (deal.get('is_active', True) or deal.get('activ', True)):
            continue

        discount = deal.get('discount_percent') or deal.get('procent_reducere', 0)
        if discount < min_discount:
            continue

        categorie = deal.get('categorie', '') or ''
        categories = deal.get('categories', [categorie])

        if any(cat.lower() in [c.lower() for c in target_categories] for cat in [categorie] + categories):
            relevant.append(deal)

    return sorted(relevant, key=lambda d: d.get('discount_percent') or d.get('procent_reducere', 0), reverse=True)


def generate_campaign_content(season: str, deals: list) -> dict:
    """Generează conținut complet pentru o campanie."""
    campaign = CAMPAIGNS.get(season)
    if not campaign:
        raise ValueError(f"Campanie necunoscută: {season}")

    now = datetime.now()
    top_deals = deals[:10]
    max_discount = max([d.get('discount_percent') or d.get('procent_reducere', 0) for d in top_deals], default=0)
    top_store = top_deals[0].get('store') or top_deals[0].get('magazin', '') if top_deals else ''

    # Subject email
    subject_template = random.choice(campaign['subject_templates'])
    subject = subject_template \
        .replace('{an}', str(now.year)) \
        .replace('{procent}', str(max_discount)) \
        .replace('{magazin}', top_store) \
        .replace('{numar}', str(len(top_deals)))

    # Lista deals pentru post
    lista_deals = ''
    for i, deal in enumerate(top_deals[:5], 1):
        title = (deal.get('title') or deal.get('titlu', ''))[:40]
        discount = deal.get('discount_percent') or deal.get('procent_reducere', 0)
        lista_deals += f"{i}. {title} — -{discount}%\n"

    # Facebook post
    fb_post = campaign['fb_template'] \
        .replace('{an}', str(now.year)) \
        .replace('{procent}', str(max_discount)) \
        .replace('{magazin}', top_store) \
        .replace('{lista_deals}', lista_deals)

    # Hashtags
    hashtags = campaign['hashtags'] + ['#reduceri', '#ghidulreducerilor', '#romania']

    return {
        'season': season,
        'name': campaign['name'],
        'emoji': campaign['emoji'],
        'generated_at': now.isoformat(),
        'deals_count': len(top_deals),
        'max_discount': max_discount,
        'email_subject': subject,
        'facebook_post': fb_post,
        'hashtags': ' '.join(hashtags[:15]),
        'top_deals': [
            {
                'title': (d.get('title') or d.get('titlu', ''))[:60],
                'discount': d.get('discount_percent') or d.get('procent_reducere', 0),
                'store': d.get('store') or d.get('magazin', ''),
                'link': d.get('affiliate_url') or d.get('link_afiliat', '')
            }
            for d in top_deals[:10]
        ]
    }


def save_campaign(content: dict):
    """Salvează campania generată."""
    campaigns_dir = DATA_DIR / 'campaigns'
    campaigns_dir.mkdir(exist_ok=True)

    filename = campaigns_dir / f"{content['season']}_{datetime.now().strftime('%Y%m%d')}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(content, f, ensure_ascii=False, indent=2)

    logger.info(f"Campanie salvată: {filename}")
    return str(filename)


def main():
    parser = argparse.ArgumentParser(description='GhidulReducerilor Campaign Creator')
    parser.add_argument('--season', help='Sezon campanie (black_friday, paste, craciun, etc.)')
    parser.add_argument('--list', action='store_true', help='Listează campaniile disponibile')
    parser.add_argument('--upcoming', action='store_true', help='Campania care urmează')
    parser.add_argument('--auto', action='store_true', help='Detectează automat sezonul curent')
    args = parser.parse_args()

    if args.list:
        print("\nCampanii disponibile:")
        for key, camp in CAMPAIGNS.items():
            print(f"  {camp['emoji']} {key} — {camp['name']} (luni: {camp['luni']})")
        return

    if args.upcoming:
        upcoming = get_upcoming_campaign(days_ahead=45)
        if upcoming:
            print(f"\nUrmătoarea campanie: {upcoming['config']['emoji']} {upcoming['config']['name']}")
            print(f"Data: {upcoming['date']} ({upcoming['days_until']} zile)")
        else:
            print("Nu există campanii în următoarele 45 de zile")
        return

    season = args.season
    if args.auto or not season:
        season = get_current_season()
        if not season:
            logger.info("Nu există sezon activ în prezent")
            upcoming = get_upcoming_campaign(days_ahead=14)
            if upcoming:
                logger.info(f"Campania viitoare: {upcoming['config']['name']} în {upcoming['days_until']} zile")
            return

    logger.info(f"=== Creare campanie: {season} ===")

    deals = load_deals_for_campaign(season)
    if not deals:
        logger.warning(f"Nu există deal-uri relevante pentru campania '{season}'")
        return

    logger.info(f"Deal-uri găsite: {len(deals)}")
    content = generate_campaign_content(season, deals)
    saved_path = save_campaign(content)

    print(f"\n=== CAMPANIE GENERATĂ: {content['name']} {content['emoji']} ===")
    print(f"Deal-uri: {content['deals_count']}")
    print(f"Reducere max: -{content['max_discount']}%")
    print(f"\nSubject email:\n  {content['email_subject']}")
    print(f"\nFacebook post preview:\n{content['facebook_post'][:200]}...")
    print(f"\nHashtags: {content['hashtags']}")
    print(f"\nSalvat în: {saved_path}")


if __name__ == '__main__':
    main()
