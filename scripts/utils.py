#!/usr/bin/env python3
"""
GhidulReducerilor.ro — Utilitare comune
Normalizare scheme, conversie linkuri, helpers.
"""

import hashlib
import re
from typing import Optional


def normalize_deal(deal: dict) -> dict:
    """
    Normalizează un deal indiferent de schema sursă.
    Acceptă atât schema veche (RO) cât și schema nouă (EN).

    Returnează deal cu TOATE câmpurile + aliasuri EN și RO,
    astfel încât atât frontend-ul (RO) cât și scripturile Python (EN) să funcționeze.
    Util și pentru deals noi din scraper (English-only) care trebuie afișate pe site.
    """
    is_active_val = deal.get('is_active') if deal.get('is_active') is not None else deal.get('activ', True)

    # Valori derivate
    title = deal.get('title') or deal.get('titlu', '')
    store = deal.get('store') or deal.get('magazine_name') or deal.get('magazin', '')
    price = deal.get('price') or deal.get('newPrice') or deal.get('pret_redus', 0)
    original_price = deal.get('originalPrice') or deal.get('original_price') or deal.get('pret_original', 0)
    discount = deal.get('discount_percent') or deal.get('procent_reducere', 0)
    aff_url = fix_profitshare_link(deal.get('affiliate_url') or deal.get('link_afiliat') or deal.get('url', ''))
    image = deal.get('image') or deal.get('imagine_url', '')
    category = (deal.get('categories') or [deal.get('categorie', '')])[0] if (deal.get('categories') or [deal.get('categorie', '')]) else ''
    scraped_at = deal.get('scraped_at') or deal.get('data_adaugare', '')
    magazine = deal.get('magazin') or store

    return {
        **deal,  # Păstrează TOATE câmpurile originale
        # ── Aliasuri EN (scripturile Python) ──────────────────────────────
        'title': title,
        'store': store,
        'price': price,
        'originalPrice': original_price,
        'discount_percent': discount,
        'affiliate_url': aff_url,
        'url': deal.get('url') or deal.get('product_url') or deal.get('link_afiliat', ''),
        'image': image,
        'categories': deal.get('categories') or [category],
        'is_active': is_active_val,
        'score': deal.get('score', 5),
        'in_stock': deal.get('in_stock', True),
        'scraped_at': scraped_at,
        'magazine_key': deal.get('magazine_key') or magazine,
        # ── Aliasuri RO (frontend Next.js) ────────────────────────────────
        'titlu': title,
        'magazin': magazine,
        'pret_redus': price,
        'pret_original': original_price,
        'procent_reducere': discount,
        'link_afiliat': aff_url,
        'imagine_url': image,
        'categorie': category,
        'data_adaugare': scraped_at,
        'activ': is_active_val,
    }


def fix_profitshare_link(link: str) -> str:
    """
    Convertește linkurile Profitshare directe în format /out/[id].
    l.profitshare.ro/l/15487990 → ghidulreducerilor.ro/out/15487990

    Linkurile l.profitshare.ro directe sunt blocate pe mobile!
    """
    if not link:
        return link

    # Pattern: l.profitshare.ro/l/NNNNNNN
    match = re.match(r'https?://l\.profitshare\.ro/l/(\d+)', link)
    if match:
        link_id = match.group(1)
        return f'https://ghidulreducerilor.ro/out/{link_id}'

    return link


def is_profitshare_direct(link: str) -> bool:
    """Verifică dacă un link este Profitshare direct (blocat pe mobile)."""
    return bool(re.match(r'https?://l\.profitshare\.ro/', link or ''))


def generate_deal_id(store: str, url: str) -> str:
    """Generează un ID unic pentru un deal."""
    return f"{store}-{hashlib.md5(url.encode()).hexdigest()[:8]}"


def calculate_real_discount(pret_nou: float, pret_vechi: float) -> float:
    """Calculează reducerea reală în procente."""
    if not pret_vechi or pret_vechi <= 0 or pret_nou >= pret_vechi:
        return 0
    return round(((pret_vechi - pret_nou) / pret_vechi) * 100, 1)


def format_price(price) -> str:
    """Formatează un preȘ pentru afișare."""
    try:
        return f"{float(price):,.0f}".replace(',', '.') + ' RON'
    except (TypeError, ValueError):
        return str(price)
