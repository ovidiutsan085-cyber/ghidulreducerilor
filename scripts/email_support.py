#!/usr/bin/env python3
"""
GhidulReducerilor.ro — AI Email Support Agent
Clasifică emailurile primite și generează răspunsuri automate.

Utilizare:
  python scripts/email_support.py --check
  python scripts/email_support.py --respond --ticket-id 123
  python scripts/email_support.py --mode auto
"""

import json
import os
import sys
import logging
import argparse
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
        logging.FileHandler('logs/email_support.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('email_support')

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / 'data'
LOGS_DIR = ROOT / 'logs'

BREVO_API_KEY = os.environ.get('BREVO_API_KEY', '')
BREVO_API_URL = 'https://api.brevo.com/v3'
SUPPORT_EMAIL = 'hello@ghidulreducerilor.ro'

# Categorii de emailuri și răspunsuri automate
EMAIL_CATEGORIES = {
    'afiliere': {
        'keywords': ['afiliere', 'afiliat', 'comision', 'parteneriat', 'colaborare', 'affiliate'],
        'auto_reply': True,
        'priority': 'medium'
    },
    'link_invalid': {
        'keywords': ['link', 'nu merge', 'eroare', '404', 'pagina nu', 'broken', 'nu funcționează'],
        'auto_reply': True,
        'priority': 'high'
    },
    'pret_gresit': {
        'keywords': ['preț greșit', 'pretul nu', 'prețul real', 'costă mai mult', 'nu mai e'],
        'auto_reply': True,
        'priority': 'high'
    },
    'dezabonare': {
        'keywords': ['dezabonare', 'dezabona', 'unsubscribe', 'opriti', 'nu mai vreau email'],
        'auto_reply': True,
        'priority': 'urgent'
    },
    'sugestie': {
        'keywords': ['sugestie', 'sugerez', 'ar fi bine', 'propun', 'magazin nou', 'adaugati'],
        'auto_reply': True,
        'priority': 'low'
    },
    'felicitare': {
        'keywords': ['multumesc', 'super', 'bravo', 'bun site', 'util', 'helpful', 'felicitari'],
        'auto_reply': True,
        'priority': 'low'
    },
    'gdpr': {
        'keywords': ['gdpr', 'date personale', 'sterg datele', 'drept de stergere', 'privacy'],
        'auto_reply': False,  # Necesită răspuns manual
        'priority': 'urgent'
    },
    'reclamatie': {
        'keywords': ['reclamatie', 'reclamație', 'plangere', 'inselat', 'înșelat', 'fals'],
        'auto_reply': False,
        'priority': 'urgent'
    },
    'general': {
        'keywords': [],
        'auto_reply': False,
        'priority': 'medium'
    }
}

AUTO_REPLIES = {
    'link_invalid': """Bună ziua,

Mulțumim că ne-ai semnalat această problemă! 🙏

Am primit notificarea ta despre link-ul care nu funcționează și vom verifica și corecta în cel mai scurt timp.

**Ce se întâmplă:**
- Uneori prețurile sau produsele se schimbă rapid la magazine
- Linkurile de afiliere pot expira sau se pot actualiza
- Verificăm automat linkurile zilnic pentru a preveni astfel de situații

**Ce poți face acum:**
- Vizitează direct magazinul: ghidulreducerilor.ro
- Caută produsul de interes - este posibil să fie listat cu link actualizat

Îți mulțumim că ne ajuți să îmbunătățim serviciul! 💪

Cu drag,
Echipa GhidulReducerilor.ro""",

    'pret_gresit': """Bună ziua,

Mulțumim pentru semnalarea prețului incorect! 🎯

Luăm această problemă foarte în serios — ne bazăm pe **Directiva Omnibus UE** care ne obligă să afișăm prețul minim din ultimele 30 de zile.

**Acțiuni imediate:**
✅ Am înregistrat sesizarea ta
✅ Vom verifica prețul real al produsului în maxim 24 de ore
✅ Dacă prețul nu este corect, vom actualiza sau elimina oferta

Ne scuze pentru inconvenienț��!

Cu drag,
Echipa GhidulReducerilor.ro""",

    'dezabonare': """Bună ziua,

Am primit cererea ta de dezabonare. 😢

**Am procesat dezabonarea ta** din lista noastră de newsletter — nu vei mai primi emailuri promoționale de la noi.

Dacă te-ai dezabonat din greșeală sau te răzgândești, te poți reabona oricând pe:
👉 https://ghidulreducerilor.ro

Îți mulțumim că ai fost abonat! Succes la cumpărături! 🛍️

Cu drag,
Echipa GhidulReducerilor.ro""",

    'sugestie': """Bună ziua,

Mulțumim pentru sugestia ta! 💡

Apreciem că îți iei timp să ne ajuți s�� îmbunătățim GhidulReducerilor.ro.

**Sugestia ta a fost înregistrat��** și va fi analizată de echipa noastr��.

Dacă sugestia ta privește un magazin nou, știi că:
- Avem parteneriate cu peste 10 magazine din România
- Extindem constant rețeaua de parteneri
- Ne poți scrie direct dac�� ai o propunere specifică de magazin

Mulțumim că ești parte din comunitatea noastră! 🙏

Cu drag,
Echipa GhidulReducerilor.ro""",

    'felicitare': """Bună ziua,

Mulțumim din suflet pentru cuvintele frumoase! 🥰

Ne bucurăm enorm că GhidulReducerilor.ro îți este util. Munca noastră are sens tocmai când aflăm că ajutăm pe cineva să economisească!

**Continuăm s�� lucră� pentru tine:**
- Verificăm zilnic sute de oferte
- Validăm reducerile (nu publicăm prețuri false)
- Adăugăm magazine noi constant

Rămâi abonat și nu rata nicio reducere! 💪

Cu drag,
Echipa GhidulReducerilor.ro""",

    'afiliere': """Bună ziua,

Mulțumim pentru interesul față de un parteneriat cu GhidulReducerilor.ro! 🤝

**Suntem activ prezenți pe:**
- Profitshare (cod afiliat: ZN4M)
- 2Performant (cont activ)

**Dacă ep�ti un magazin care dorește să fie listat:**
Trimite-ne detalii despre:
- Magazinul tău și categoriile de produse
- Rețeaua de afiliere utilizat��
- Comisioanele oferite

**Dacă ep�ti un creator de conținut:**
Ne pare rău, momentan nu avem program de sub-afiliere.

Vom rčspunde în maxim 48 de ore!

Cu drag,
Echipa GhidulReducerilor.ro"""
}


def classify_email(subject: str, body: str) -> str:
    """Clasifică un email pe baza textului."""
    text = f"{subject} {body}".lower()

    # Verifică dezabonare cu prioritate maximă
    for keyword in EMAIL_CATEGORIES['dezabonare']['keywords']:
        if keyword in text:
            return 'dezabonare'

    # Verifică GDPR
    for keyword in EMAIL_CATEGORIES['gdpr']['keywords']:
        if keyword in text:
            return 'gdpr'

    # Verifică reclamații
    for keyword in EMAIL_CATEGORIES['reclamatie']['keywords']:
        if keyword in text:
            return 'reclamatie'

    # Restul categoriilor
    scores = {}
    for category, config in EMAIL_CATEGORIES.items():
        if category in ['dezabonare', 'gdpr', 'reclamatie', 'general']:
            continue
        score = sum(1 for kw in config['keywords'] if kw in text)
        if score > 0:
            scores[category] = score

    if scores:
        return max(scores, key=scores.get)

    return 'general'


def generate_auto_reply(category: str, sender_name: str = '') -> Optional[str]:
    """Generează un răspuns automat pentru categoria dat��."""
    category_config = EMAIL_CATEGORIES.get(category, {})

    if not category_config.get('auto_reply', False):
        return None

    template = AUTO_REPLIES.get(category)
    if not template:
        return None

    if sender_name:
        template = template.replace('Bună ziua,', f'Bună ziua {sender_name},')

    return template


def process_ticket(ticket: dict, dry_run: bool = False) -> dict:
    """Procesează un ticket de suport."""
    subject = ticket.get('subject', '')
    body = ticket.get('body', '')
    sender_email = ticket.get('from_email', '')
    sender_name = ticket.get('from_name', '')

    category = classify_email(subject, body)
    category_config = EMAIL_CATEGORIES.get(category, EMAIL_CATEGORIES['general'])

    result = {
        'ticket_id': ticket.get('id', ''),
        'category': category,
        'priority': category_config.get('priority', 'medium'),
        'auto_reply_sent': False,
        'needs_manual_reply': not category_config.get('auto_reply', False),
        'processed_at': datetime.now(timezone.utc).isoformat()
    }

    logger.info(f"Ticket {ticket.get('id', 'new')}: [{category}] de la {sender_email}")

    # Trimite răspuns automat dac�� e cazul
    auto_reply = generate_auto_reply(category, sender_name)
    if auto_reply and sender_email:
        if dry_run:
            logger.info(f"[DRY RUN] Auto-reply la {sender_email}:\n{auto_reply[:200]}...")
            result['auto_reply_sent'] = True
        else:
            sent = send_email_reply(sender_email, sender_name, subject, auto_reply)
            result['auto_reply_sent'] = sent

    # Log urgent issues
    if category_config.get('priority') == 'urgent':
        logger.warning(f"URGENT TICKET [{category}]: {subject[:100]} de la {sender_email}")

    return result


def send_email_reply(to_email: str, to_name: str, original_subject: str, reply_body: str) -> bool:
    """Trimite un email de răspuns via Brevo."""
    if not BREVO_API_KEY:
        logger.error("BREVO_API_KEY lipsește!")
        return False

    subject = f"Re: {original_subject}" if not original_subject.startswith('Re:') else original_subject

    # Convertește text plain în HTML simplu
    html_body = reply_body.replace('\n\n', '</p><p>').replace('\n', '<br>')
    html_body = f"<p>{html_body}</p>"

    headers = {
        'api-key': BREVO_API_KEY,
        'Content-Type': 'application/json'
    }

    email_data = {
        "sender": {"name": "GhidulReducerilor.ro", "email": SUPPORT_EMAIL},
        "to": [{"email": to_email, "name": to_name or to_email}],
        "replyTo": {"email": SUPPORT_EMAIL},
        "subject": subject,
        "htmlContent": html_body,
        "textContent": reply_body
    }

    try:
        response = requests.post(
            f'{BREVO_API_URL}/smtp/email',
            headers=headers,
            json=email_data,
            timeout=30
        )

        if response.status_code == 201:
            logger.info(f"Răspuns trimis la {to_email}")
            return True
        else:
            logger.error(f"Eroare trimitere email: {response.status_code} — {response.text[:200]}")
            return False

    except Exception as e:
        logger.error(f"Eroare conexiune: {e}")
        return False


def fetch_unread_emails() -> list:
    """
    Verifică emailurile necitite via Brevo Conversations API.
    Returneaz�� lista de tickete noi.
    """
    if not BREVO_API_KEY:
        logger.error("BREVO_API_KEY lipsește!")
        return []

    headers = {
        'api-key': BREVO_API_KEY,
        'Content-Type': 'application/json'
    }

    try:
        # Conversations API
        response = requests.get(
            f'{BREVO_API_URL}/conversations/messages',
            headers=headers,
            params={'groupId': os.environ.get('BREVO_INBOX_ID', ''), 'limit': 20},
            timeout=15
        )

        if response.status_code == 200:
            messages = response.json().get('messages', [])
            logger.info(f"Emailuri noi: {len(messages)}")
            return messages
        else:
            logger.warning(f"Nu s-au putut accesa emailurile: {response.status_code}")
            return []

    except Exception as e:
        logger.error(f"Eroare fetch emailuri: {e}")
        return []


def save_support_log(results: list):
    """Salveaz�� log-ul de suport."""
    log_path = LOGS_DIR / f"support_log_{datetime.now().strftime('%Y%m%d')}.json"

    existing = []
    if log_path.exists():
        with open(log_path, 'r', encoding='utf-8') as f:
            existing = json.load(f)

    existing.extend(results)

    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    logger.info(f"Log suport actualizat: {log_path}")


def main():
    parser = argparse.ArgumentParser(description='GhidulReducerilor Email Support')
    parser.add_argument('--check', action='store_true', help='Verifică emailuri noi')
    parser.add_argument('--mode', choices=['auto', 'manual'], default='auto')
    parser.add_argument('--dry-run', action='store_true', help='Proceseaz�� dar nu trimite')
    args = parser.parse_args()

    logger.info(f"=== Email Support Agent ===")

    if args.check or args.mode == 'auto':
        emails = fetch_unread_emails()

        results = []
        for email in emails:
            ticket = {
                'id': email.get('id', ''),
                'subject': email.get('subject', ''),
                'body': email.get('body', email.get('text', '')),
                'from_email': email.get('from', {}).get('email', ''),
                'from_name': email.get('from', {}).get('name', '')
            }
            result = process_ticket(ticket, dry_run=args.dry_run)
            results.append(result)

        if results:
            save_support_log(results)
            urgent = [r for r in results if r.get('priority') == 'urgent']
            auto_replied = [r for r in results if r.get('auto_reply_sent')]
            manual = [r for r in results if r.get('needs_manual_reply')]

            print(f"\n=== SUMAR SUPORT ===")
            print(f"Total procesate: {len(results)}")
            print(f"Auto-replicate: {len(auto_replied)}")
            print(f"Necesită răspuns manual: {len(manual)}")
            print(f"URGENT: {len(urgent)}")

            if urgent:
                print(f"\n⚠️ Tickete URGENTE:")
                for r in urgent:
                    print(f"  - {r['ticket_id']}: [{r['category']}]")
        else:
            print("Nu există emailuri noi de procesat.")


if __name__ == '__main__':
    main()
