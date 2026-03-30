#!/usr/bin/env python3
"""
GhidulReducerilor.ro — SEO Audit Script
Verifică SEO tehnic, sitemap, meta tags, keywords și performanța paginilor.

Utilizare:
  python scripts/seo_audit.py --mode full
  python scripts/seo_audit.py --mode quick
  python scripts/seo_audit.py --url https://ghidulreducerilor.ro/reduceri/emag
"""

import json
import os
import sys
import logging
import argparse
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urljoin
from typing import Optional

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    missing = []
    try:
        import requests
    except ImportError:
        missing.append('requests')
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        missing.append('beautifulsoup4')
    if missing:
        print(f"Instalează: pip install {' '.join(missing)}")
        sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('logs/seo_audit.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('seo_audit')

ROOT = Path(__file__).parent.parent
CONFIG_DIR = ROOT / 'config'
LOGS_DIR = ROOT / 'logs'

BASE_URL = 'https://ghidulreducerilor.ro'
REQUEST_TIMEOUT = 20

PAGES_TO_AUDIT = [
    '/',
    '/reduceri',
    '/coduri-promotionale',
    '/magazine',
    '/reduceri/emag',
    '/reduceri/fashiondays',
    '/reduceri/notino',
    '/reduceri/answear',
    '/reduceri/decathlon',
]

TITLE_MIN_LEN = 30
TITLE_MAX_LEN = 60
DESC_MIN_LEN = 120
DESC_MAX_LEN = 160
H1_REQUIRED = True


def load_keywords() -> dict:
    """Încarcă configurația de keywords SEO."""
    keywords_path = CONFIG_DIR / 'seo_keywords.json'
    if keywords_path.exists():
        with open(keywords_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def create_session() -> requests.Session:
    """Creează sesiune HTTP."""
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'GhidulReducerilor-SEOAudit/1.0 (https://ghidulreducerilor.ro) ',
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'ro-RO,ro;q=0.9'
    })
    return session


def audit_page(session: requests.Session, url: str) -> dict:
    """Auditează o paginăși returnează issues + scor."""
    result = {
        'url': url,
        'status_code': None,
        'response_time_ms': None,
        'issues': [],
        'warnings': [],
        'passed': [],
        'score': 0,
        'title': None,
        'description': None,
        'h1': None,
        'canonical': None,
        'robots': None,
        'og_title': None,
        'og_description': None,
        'structured_data': False,
        'checked_at': datetime.now(timezone.utc).isoformat()
    }

    start_time = time.time()

    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        elapsed = round((time.time() - start_time) * 1000)
        result['response_time_ms'] = elapsed
        result['status_code'] = response.status_code

        # ===== Status Code =====
        if response.status_code == 200:
            result['passed'].append('Status 200 OK')
        elif response.status_code in [301, 302]:
            result['warnings'].append(f'Redirect {response.status_code} → {response.url}')
        else:
            result['issues'].append(f'Status code neașteptat: {response.status_code}')
            return result

        # ===== Response Time =====
        if elapsed < 1000:
            result['passed'].append(f'Timp răspuns rapid: {elapsed}ms')
        elif elapsed < 3000:
            result['warnings'].append(f'Timp răspuns mediu: {elapsed}ms (recomandat <1s)')
        else:
            result['issues'].append(f'Timp răspuns lent: {elapsed}ms (prag critic: >3s)')

        # ===== Parse HTML =====
        soup = BeautifulSoup(response.content, 'html.parser')

        # ===== Title Tag =====
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text().strip()
            result['title'] = title
            title_len = len(title)

            if title_len < TITLE_MIN_LEN:
                result['issues'].append(f'Title prea scurt: {title_len} chars (min {TITLE_MIN_LEN})')
            elif title_len > TITLE_MAX_LEN:
                result['warnings'].append(f'Title prea lung: {title_len} chars (max {TITLE_MAX_LEN})')
            else:
                result['passed'].append(f'Title OK: {title_len} chars')

            # Verifică brand în title
            if 'ghidulreducerilor' in title.lower():
                result['passed'].append('Brand în title')
            else:
                result['warnings'].append('Brand lipsă din title')
        else:
            result['issues'].append('TAG TITLE LIPSĂ!')

        # ===== Meta Description =====
        desc_tag = soup.find('meta', attrs={'name': 'description'})
        if desc_tag:
            desc = desc_tag.get('content', '').strip()
            result['description'] = desc
            desc_len = len(desc)

            if desc_len < DESC_MIN_LEN:
                result['issues'].append(f'Meta description prea scurtă: {desc_len} chars (min {DESC_MIN_LEN})')
            elif desc_len > DESC_MAX_LEN:
                result['warnings'].append(f'Meta description prea lungă: {desc_len} chars (max {DESC_MAX_LEN})')
            else:
                result['passed'].append(f'Meta description OK: {desc_len} chars')
        else:
            result['issues'].append('META DESCRIPTION LIPSĂ!')

        # ===== H1 Tag =====
        h1_tags = soup.find_all('h1')
        if len(h1_tags) == 0:
            result['issues'].append('H1 LIPSĂ!')
        elif len(h1_tags) == 1:
            result['h1'] = h1_tags[0].get_text().strip()
            result['passed'].append(f'H1 OK: "{result["h1"][:50]}"')
        else:
            result['warnings'].append(f'Multiple H1-uri ({len(h1_tags)}) — recomandat 1')
            result['h1'] = h1_tags[0].get_text().strip()

        # ===== Canonical Tag =====
        canonical_tag = soup.find('link', attrs={'rel': 'canonical'})
        if canonical_tag:
            result['canonical'] = canonical_tag.get('href', '')
            result['passed'].append('Canonical tag prezent')
        else:
            result['warnings'].append('Canonical tag lipsă')

        # ===== Robots Meta =====
        robots_tag = soup.find('meta', attrs={'name': 'robots'})
        if robots_tag:
            robots_content = robots_tag.get('content', '')
            result['robots'] = robots_content
            if 'noindex' in robots_content.lower():
                result['issues'].append(f'PAGINA NOINDEX: {robots_content}')
            else:
                result['passed'].append(f'Robots OK: {robots_content}')

        # ===== Open Graph =====
        og_title = soup.find('meta', attrs={'property': 'og:title'})
        og_desc = soup.find('meta', attrs={'property': 'og:description'})
        og_image = soup.find('meta', attrs={'property': 'og:image'})

        if og_title:
            result['og_title'] = og_title.get('content', '')
            result['passed'].append('OG Title prezent')
        else:
            result['warnings'].append('OG Title lipsă')

        if og_desc:
            result['og_description'] = og_desc.get('content', '')
        else:
            result['warnings'].append('OG Description lipsă')

        if og_image:
            result['passed'].append('OG Image prezent')
        else:
            result['warnings'].append('OG Image lipsă')

        # ===== Structured Data (JSON-LD) =====
        json_ld_scripts = soup.find_all('script', attrs={'type': 'application/ld+json'})
        if json_ld_scripts:
            result['structured_data'] = True
            result['passed'].append(f'Structured data prezent ({len(json_ld_scripts)} blocuri) ')
        else:
            result['warnings'].append('Structured data (JSON-LD) lipsă ℔ recomandat pentru produse/oferte')

        # ===== Images ALT text =====
        images = soup.find_all('img')
        images_without_alt = [img for img in images if not img.get('alt')]
        if images_without_alt:
            count = len(images_without_alt)
            if count > 5:
                result['issues'].append(f'{count} imagini fără atribut ALT ~')
            else:
                result['warnings'].append(f'{count} imagini fără ALT')
        elif images:
            result['passed'].append(f'Toate {len(images)} imagini au ALT text')

        # ===== Calculează scorul =====
        max_score = 100
        deductions = len(result['issues']) * 15 + len(result['warnings']) * 5
        result['score'] = max(0, max_score - deductions)

    except requests.exceptions.Timeout:
        result['issues'].append(f'Timeout după {REQUEST_TIMEOUT}s')
    except requests.exceptions.ConnectionError:
        result['issues'].append('Eroare de conexiune — site-ul nu răspunde')
    except Exception as e:
        result['issues'].append(f'Eroare audit: {str(e)[:100]}')

    return result


def check_sitemap(session: requests.Session) -> dict:
    """Verifică sitemap.xml."""
    sitemap_url = f"{BASE_URL}/sitemap.xml"
    result = {
        'url': sitemap_url,
        'accessible': False,
        'url_count': 0,
        'issues': []
    }

    try:
        response = session.get(sitemap_url, timeout=15)
        if response.status_code == 200:
            result['accessible'] = True
            # Numără URL-urile din sitemap
            soup = BeautifulSoup(response.content, 'xml')
            urls = soup.find_all('url')
            result['url_count'] = len(urls)
            logger.info(f"Sitemap OK: {len(urls)} URL-uri")
        else:
            result['issues'].append(f'Sitemap returnează {response.status_code}')
    except Exception as e:
        result['issues'].append(f'Sitemap inaccesibil: {str(e)[:100]}')

    return result


def check_robots_txt(session: requests.Session) -> dict:
    """Verifică robots.txt."""
    robots_url = f"{BASE_URL}/robots.txt"
    result = {
        'url': robots_url,
        'accessible': False,
        'has_sitemap': False,
        'disallowed_paths': [],
        'issues': []
    }

    try:
        response = session.get(robots_url, timeout=10)
        if response.status_code == 200:
            result['accessible'] = True
            content = response.text

            # Verifică dacă conține Sitemap
            if 'Sitemap:' in content:
                result['has_sitemap'] = True
            else:
                result['issues'].append('robots.txt nu conține referință la Sitemap')

            # Verifică Disallow paths
            for line in content.split('\n'):
                if line.strip().startswith('Disallow:'):
                    path = line.split(':', 1)[1].strip()
                    if path:
                        result['disallowed_paths'].append(path)
        else:
            result['issues'].append(f'robots.txt returnează {response.status_code}')
    except Exception as e:
        result['issues'].append(f'robots.txt inaccesibil: {str(e)[:100]}')

    return result


def check_keyword_density(session: requests.Session, keywords: dict) -> dict:
    """Verifică prezența keyword-urilor principale pe homepage."""
    result = {'present': [], 'missing': []}

    try:
        response = session.get(BASE_URL, timeout=REQUEST_TIMEOUT)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            # Extrage text vizibil
            for script in soup(['script', 'style']):
                script.decompose()
            text = soup.get_text().lower()

            main_keywords = keywords.get('keywords_principale', [])
            for kw in main_keywords[:10]:  # Verifică primele 10
                if kw.lower() in text:
                    result['present'].append(kw)
                else:
                    result['missing'].append(kw)
    except Exception as e:
        logger.error(f"Eroare keyword check: {e}")

    return result


def generate_seo_report(audit_results: list, sitemap: dict, robots: dict, keywords_check: dict) -> dict:
    """Generează raportul complet SEO."""
    total_issues = sum(len(r['issues']) for r in audit_results)
    total_warnings = sum(len(r['warnings']) for r in audit_results)
    avg_score = round(sum(r['score'] for r in audit_results) / len(audit_results), 1) if audit_results else 0

    # Paginile cu cele mai multe probleme
    critical_pages = sorted(audit_results, key=lambda r: len(r['issues']), reverse=True)[:3]

    report = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'base_url': BASE_URL,
        'pages_audited': len(audit_results),
        'avg_score': avg_score,
        'total_issues': total_issues,
        'total_warnings': total_warnings,
        'sitemap': sitemap,
        'robots_txt': robots,
        'keywords_check': keywords_check,
        'page_results': audit_results,
        'critical_pages': [
            {'url': p['url'], 'score': p['score'], 'issues': p['issues'][:3]}
            for p in critical_pages
            if p['issues']
        ],
        'summary': {
            'excellent': len([r for r in audit_results if r['score'] >= 80]),
            'good': len([r for r in audit_results if 60 <= r['score'] < 80]),
            'needs_work': len([r for r in audit_results if r['score'] < 60])
        }
    }

    return report


def save_report(report: dict):
    """Salvează raportul SEO."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    report_path = LOGS_DIR / f"seo_audit_{timestamp}.json"

    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info(f"Raport SEO salvat: {report_path}")
    return str(report_path)


def main():
    parser = argparse.ArgumentParser(description='GhidulReducerilor SEO Audit')
    parser.add_argument('--mode', choices=['full', 'quick'], default='quick')
    parser.add_argument('--url', help='Auditează doar un URL specific')
    args = parser.parse_args()

    logger.info(f"=== SEO Audit — mod: {args.mode} ===")

    session = create_session()
    keywords = load_keywords()

    if args.url:
        pages = [args.url]
    elif args.mode == 'quick':
        pages = [BASE_URL + p for p in PAGES_TO_AUDIT[:4]]  # Primele 4 pagini
    else:
        pages = [BASE_URL + p for p in PAGES_TO_AUDIT]

    # Auditează paginile
    audit_results = []
    for url in pages:
        logger.info(f"Auditez: {url}")
        result = audit_page(session, url)
        audit_results.append(result)
        time.sleep(0.5)  # Politicos cu serverul

    # Verifică sitemap și robots.txt
    sitemap = check_sitemap(session)
    robots = check_robots_txt(session)
    keywords_check = check_keyword_density(session, keywords)

    # Generează raport
    report = generate_seo_report(audit_results, sitemap, robots, keywords_check)
    report_path = save_report(report)

    # Print sumar
    print(f"\n=== RAPORT SEO AUDIT ===")
    print(f"Pagini auditate: {report['pages_audited']}")
    print(f"Scor mediu: {report['avg_score']}/100")
    print(f"Total issues: {report['total_issues']}")
    print(f"Total warnings: {report['total_warnings']}")

    print(f"\nSumar pagini:")
    print(f"  ✅ Excelent (≥80): {report['summary']['excellent']}")
    print(f"  ⚠️  Bun (60-79): {report['summary']['good']}")
    print(f"  ❌ Necesită lucru (<60): {report['summary']['needs_work']}")

    print(f"\nSitemap: {'✅ OK' if sitemap['accessible'] else '❌ PROBLEMĂ'} ({sitemap.get('url_count', 0)} URL-uri)")
    print(f"robots.txt: {'✅ OK' if robots['accessible'] else '❌ PROBLEMĂ'}")

    if keywords_check.get('missing'):
        print(f"\nKeywords lipsă de pe homepage: {', '.join(keywords_check['missing'][:5])}")

    if report['critical_pages']:
        print(f"\nPagini critice:")
        for page in report['critical_pages']:
            print(f"  - {page['url']}: scor {page['score']}, {len(page['issues'])} issues")

    print(f"\nRaport complet: {report_path}")

    return report


if __name__ == '__main__':
    main()
