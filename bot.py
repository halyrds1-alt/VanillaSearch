#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vanilla Search Bot — ФИНАЛЬНАЯ ВЕРСИЯ
ВСЁ ЧЕРЕЗ INLINE КНОПКИ | АНИМАЦИИ | АДМИН-ПАНЕЛЬ
tg: @VanillaSearch | Поддержка: @bothkm
"""

import telebot
from telebot import types
import requests
import json
import re
import sqlite3
import os
import time
import random
import hashlib
import threading
from datetime import datetime, timedelta
from collections import defaultdict
import base64

# ---------- КОНФИГ ----------
MAIN_TOKEN = "8311685829:AAHgGN8usDot7UXkuqA2g7IJJqarQpGQceQ"
ADMIN_ID = 6747528307
LOG_CHANNEL = "@Loginvanilla"
REQUIRED_REFERRALS_FOR_UNLIMITED = 5
STARS_PRICE = 10

CHANNELS = [
    {"username": "@VanillaSearch", "link": "https://t.me/VanillaSearch"},
    {"username": "@ClanVerify", "link": "https://t.me/ClanVerify"}
]

# API
BIGBASE_TOKEN = "jLG0gj81FNzYETkJx2ctD_7PodUcE8xB"
BIGBASE_URL = "https://bigbase.top/api/search"
VK_TOKEN = "0af157510af157510af15751aa0a89e69600af10af157516a0bc15996e74fe2b440998c"
IPDATA_KEY = "c335d87f4e99ce6a747f8628bea61368f7274ff83b39d019c4ed0731"

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vanilla_search.db")
LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")

# ---------- БАЗА ДАННЫХ ----------
def init_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        reg_date TEXT,
        last_active TEXT,
        is_captcha_passed INTEGER DEFAULT 0,
        is_subscribed INTEGER DEFAULT 0,
        is_unlimited INTEGER DEFAULT 0,
        free_searches INTEGER DEFAULT 5,
        search_count INTEGER DEFAULT 0,
        ban_status INTEGER DEFAULT 0,
        subscription_until TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS search_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        query TEXT,
        search_type TEXT,
        result TEXT,
        date TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS masked_numbers (
        user_id INTEGER,
        phone TEXT,
        date TEXT,
        PRIMARY KEY (user_id, phone)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        referrer_id INTEGER,
        referred_id INTEGER,
        date TEXT,
        is_verified INTEGER DEFAULT 0
    )''')
    # проверка колонок
    c.execute("PRAGMA table_info(users)")
    existing = [col[1] for col in c.fetchall()]
    for col in ['is_unlimited', 'free_searches', 'ban_status', 'subscription_until']:
        if col not in existing:
            c.execute(f"ALTER TABLE users ADD COLUMN {col} DEFAULT 0")
    if 'free_searches' not in existing:
        c.execute("ALTER TABLE users ADD COLUMN free_searches INTEGER DEFAULT 5")
    conn.commit()
    conn.close()
    print(f"[DB] Готово: {DB_PATH}")

def add_user(user_id, username, first_name, last_name, referrer_id=0):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not c.fetchone():
        c.execute("INSERT INTO users (user_id, username, first_name, last_name, reg_date, last_active) VALUES (?,?,?,?,?,?)",
                  (user_id, username or '', first_name or '', last_name or '', datetime.now().isoformat(), datetime.now().isoformat()))
        if referrer_id and referrer_id != user_id:
            c.execute("INSERT INTO referrals (referrer_id, referred_id, date) VALUES (?,?,?)",
                      (referrer_id, user_id, datetime.now().isoformat()))
    else:
        c.execute("UPDATE users SET last_active = ? WHERE user_id = ?", (datetime.now().isoformat(), user_id))
    conn.commit()
    conn.close()

def update_captcha(user_id):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c = conn.cursor()
    c.execute("UPDATE users SET is_captcha_passed = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def is_captcha_passed(user_id):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c = conn.cursor()
    c.execute("SELECT is_captcha_passed FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row and row[0] == 1

def update_subscription(user_id, status):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c = conn.cursor()
    c.execute("UPDATE users SET is_subscribed = ? WHERE user_id = ?", (status, user_id))
    conn.commit()
    conn.close()

def is_subscribed(user_id):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c = conn.cursor()
    c.execute("SELECT is_subscribed FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row and row[0] == 1

def set_unlimited(user_id):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c = conn.cursor()
    c.execute("UPDATE users SET is_unlimited = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def is_unlimited(user_id):
    if user_id == ADMIN_ID:
        return True
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c = conn.cursor()
    c.execute("SELECT is_unlimited FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row and row[0] == 1

def add_subscription_days(user_id, days):
    """Добавляет подписку на days дней (если days=0 – бессрочно)"""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c = conn.cursor()
    if days == 0:
        c.execute("UPDATE users SET is_unlimited = 1 WHERE user_id = ?", (user_id,))
    else:
        c.execute("SELECT subscription_until FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        current = datetime.fromisoformat(row[0]) if row and row[0] else datetime.now()
        new_end = current + timedelta(days=days)
        c.execute("UPDATE users SET subscription_until = ? WHERE user_id = ?", (new_end.isoformat(), user_id))
    conn.commit()
    conn.close()

def remove_subscription(user_id):
    """Убирает подписку и бессрочку, возвращает к бесплатным поискам"""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c = conn.cursor()
    c.execute("UPDATE users SET is_unlimited = 0, subscription_until = NULL WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def has_active_subscription(user_id):
    if user_id == ADMIN_ID:
        return True
    if is_unlimited(user_id):
        return True
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c = conn.cursor()
    c.execute("SELECT subscription_until FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row and row[0]:
        return datetime.fromisoformat(row[0]) > datetime.now()
    return False

def add_free_searches(user_id, amount):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c = conn.cursor()
    c.execute("UPDATE users SET free_searches = free_searches + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def remove_free_searches(user_id, amount):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c = conn.cursor()
    c.execute("UPDATE users SET free_searches = free_searches - ? WHERE user_id = ? AND free_searches >= ?", (amount, user_id, amount))
    conn.commit()
    conn.close()

def decrement_free_search(user_id):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c = conn.cursor()
    c.execute("UPDATE users SET free_searches = free_searches - 1 WHERE user_id = ? AND free_searches > 0", (user_id,))
    conn.commit()
    conn.close()

def get_free_searches(user_id):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c = conn.cursor()
    c.execute("SELECT free_searches FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def can_search(user_id):
    """Проверяет, может ли пользователь выполнить поиск"""
    if user_id == ADMIN_ID:
        return True
    if has_active_subscription(user_id):
        return True
    free = get_free_searches(user_id)
    if free > 0:
        return True
    return False

def inc_search(user_id):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c = conn.cursor()
    c.execute("UPDATE users SET search_count = search_count + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def add_search_history(user_id, query, search_type, result):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c = conn.cursor()
    c.execute("INSERT INTO search_history (user_id, query, search_type, result, date) VALUES (?,?,?,?,?)",
              (user_id, query, search_type, result[:2000], datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_user_history(user_id, limit=20):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c = conn.cursor()
    c.execute("SELECT query, search_type, date FROM search_history WHERE user_id = ? ORDER BY date DESC LIMIT ?", (user_id, limit))
    rows = c.fetchall()
    conn.close()
    return rows

def get_total_searches():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c = conn.cursor()
    c.execute("SELECT SUM(search_count) FROM users")
    row = c.fetchone()
    conn.close()
    return row[0] or 0

def get_today_searches():
    today = datetime.now().strftime('%Y-%m-%d')
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM search_history WHERE date LIKE ?", (f"{today}%",))
    row = c.fetchone()
    conn.close()
    return row[0] or 0

def is_banned(user_id):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c = conn.cursor()
    c.execute("SELECT ban_status FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row and row[0] == 1

def ban_user(user_id, status):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c = conn.cursor()
    c.execute("UPDATE users SET ban_status = ? WHERE user_id = ?", (status, user_id))
    conn.commit()
    conn.close()

def get_all_users(limit=50):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c = conn.cursor()
    c.execute("SELECT user_id, username, first_name, last_name, reg_date, search_count FROM users ORDER BY reg_date DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_all_user_ids():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

# ---------- РЕФЕРАЛЫ ----------
def get_referral_count(user_id):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ? AND is_verified = 1", (user_id,))
    count = c.fetchone()[0]
    conn.close()
    return count

def verify_referral(referred_id):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c = conn.cursor()
    c.execute("SELECT referrer_id FROM referrals WHERE referred_id = ? AND is_verified = 0", (referred_id,))
    row = c.fetchone()
    if row:
        referrer_id = row[0]
        c.execute("UPDATE referrals SET is_verified = 1 WHERE referred_id = ?", (referred_id,))
        new_count = get_referral_count(referrer_id) + 1
        if new_count >= REQUIRED_REFERRALS_FOR_UNLIMITED:
            set_unlimited(referrer_id)
            try:
                bot.send_message(referrer_id, "🎉 Поздравляем! Вы пригласили 5 друзей. Теперь у вас **безлимитный доступ** навсегда!", parse_mode='Markdown')
            except:
                pass
            send_log(referrer_id, "system", f"Достигнуто 5 рефералов, выдана бессрочная подписка", "unlimited")
        conn.commit()
        send_log(referrer_id, "system", f"Реферал {referred_id} прошёл каптчу", "referral")
    conn.close()

# ---------- МАСКИРОВАННЫЕ НОМЕРА ----------
def add_masked_number(user_id, phone):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO masked_numbers (user_id, phone, date) VALUES (?,?,?)",
              (user_id, phone, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def is_number_masked(phone):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c = conn.cursor()
    c.execute("SELECT 1 FROM masked_numbers WHERE phone = ?", (phone,))
    row = c.fetchone()
    conn.close()
    return row is not None

# ---------- ЛОГ В КАНАЛ ----------
def send_log(user_id, username, query, search_type, extra=""):
    if user_id == ADMIN_ID:
        return
    try:
        bot.send_message(LOG_CHANNEL, f"🔍 Пользователь {user_id} (@{username}) ввёл: {query} (тип: {search_type}) {extra}", protect_content=True)
    except:
        pass

# ---------- ОБЩИЕ ФУНКЦИИ ----------
captcha_storage = {}
def generate_captcha():
    n1 = random.randint(1, 10)
    n2 = random.randint(1, 10)
    ans = str(n1 + n2)
    cid = hashlib.md5(f"{time.time()}{random.random()}".encode()).hexdigest()[:8]
    captcha_storage[cid] = ans
    return cid, f"{n1} + {n2}"

def check_captcha(cid, ans):
    if cid not in captcha_storage:
        return False
    correct = captcha_storage[cid]
    del captcha_storage[cid]
    return ans.strip() == correct

# ---------- ПОИСК ЧЕРЕЗ BIGBASE ----------
def search_bigbase(query):
    headers = {"Authorization": BIGBASE_TOKEN, "Content-Type": "application/json"}
    digits = re.sub(r'\D', '', query)
    if len(digits) >= 10 and len(digits) <= 12:
        fmts = [f"+{digits}", digits, f"8{digits[1:]}", digits[1:]]
        for fmt in fmts[:3]:
            try:
                r = requests.post(BIGBASE_URL, json={"search": fmt, "page": 1}, headers=headers, timeout=30)
                if r.status_code == 200:
                    data = r.json()
                    if data and (data.get('dossier') or data.get('connections')):
                        return data
            except:
                continue
    else:
        try:
            r = requests.post(BIGBASE_URL, json={"search": query, "page": 1}, headers=headers, timeout=30)
            if r.status_code == 200:
                data = r.json()
                if data:
                    return data
        except:
            pass
    return None

# ---------- HTML ОТЧЁТ ----------
def get_logo_base64():
    if os.path.exists(LOGO_PATH):
        with open(LOGO_PATH, 'rb') as f:
            return base64.b64encode(f.read()).decode()
    return None

def generate_html_report(query, data, search_type, masked=False):
    logo = get_logo_base64()
    now = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
    if masked:
        return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Vanilla Search – {query}</title><meta name="viewport" content="width=device-width, initial-scale=1">
<style>*{{margin:0;padding:0;box-sizing:border-box;}}body{{background:#1a1a1a;font-family:'Segoe UI',sans-serif;padding:30px 20px;}}.card{{max-width:1000px;margin:0 auto;background:#2d2d2d;border-radius:32px;overflow:hidden;color:#e0e0e0;}}.header{{background:#3a3a3a;padding:30px 25px;text-align:center;}}.title{{font-size:28px;font-weight:800;color:#fff;}}.badge{{background:#555;display:inline-block;padding:6px 18px;border-radius:40px;margin-top:15px;}}.content{{padding:30px;}}.section{{background:#3a3a3a;border-radius:24px;margin-bottom:25px;border:1px solid #555;}}.section-title{{background:#444;padding:16px 24px;font-weight:700;border-bottom:1px solid #555;}}.section-body{{padding:20px 24px;text-align:center;}}.star-line{{font-size:24px;letter-spacing:4px;color:#888;margin:10px 0;}}.footer{{background:#222;padding:18px;text-align:center;color:#888;border-top:1px solid #444;}}.footer a{{color:#aaa;text-decoration:none;}}</style>
</head>
<body>
<div class="card">
    <div class="header"><div class="logo">{'<img src="data:image/png;base64,'+logo+'" style="max-height:70px">' if logo else '🌿'}</div><div class="title">VANILLA SEARCH</div><div class="badge">🔍 {search_type.upper()} · {query}</div></div>
    <div class="content"><div class="section"><div class="section-title">📋 ДАННЫЕ СКРЫТЫ</div><div class="section-body"><div class="star-line">******************************************</div><div class="star-line">************ МАСКИРОВКА ************</div><div class="star-line">******************************************</div></div></div></div>
    <div class="footer">Vanilla Search · <a href="https://t.me/bothkm">by bothkm.t.me</a><br>⚠️ Все данные выдуманы, совпадения случайны</div>
</div>
</body>
</html>"""

    # Полный отчёт
    head = data.get('dossier', {}).get('head', {}) if data else {}
    operator = head.get('phone_operator', 'Неизвестно')
    region = head.get('phone_region', 'Неизвестно')
    country = head.get('phone_country_info', 'Неизвестно')
    persons = data.get('connections', {}).get('person', []) if data else []
    sources = set()
    for rec in data.get('records', []):
        name = rec.get('base_info', {}).get('name', '')
        if name:
            sources.add(name)

    persons_html = ""
    for i, person in enumerate(persons[:15], 1):
        person_head = person.get('head', {})
        name = person_head.get('title', 'Неизвестно')
        birthday = f'<div class="person-detail"><div class="person-icon">🎂</div><div class="person-label">Дата</div><div class="person-value">{person_head["head_birthday"]}</div></div>' if person_head.get('head_birthday') else ''
        phones_html = ''.join([f'<div class="person-detail"><div class="person-icon">📱</div><div class="person-label">Телефон</div><div class="person-value">{ph["value"]}</div></div>' for ph in person.get('phone', [])[:3] if isinstance(ph, dict) and ph.get('value')])
        emails_html = ''.join([f'<div class="person-detail"><div class="person-icon">📧</div><div class="person-label">Email</div><div class="person-value">{em["value"]}</div></div>' for em in person.get('email', [])[:2] if isinstance(em, dict) and em.get('value')])
        addrs_html = ''.join([f'<div class="person-detail"><div class="person-icon">🏠</div><div class="person-label">Адрес</div><div class="person-value">{ad["full"]}</div></div>' for ad in person.get('address_place', [])[:1] if isinstance(ad, dict) and ad.get('full')])
        persons_html += f'<div class="person-card"><div class="person-name">👤 [{i}] {name}</div>{birthday}{phones_html}{emails_html}{addrs_html}</div>'

    sources_html = ''.join([f'<div class="source-tag">📌 {s}</div>' for s in list(sources)[:30]])

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Vanilla Search – {query}</title><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}body{{background:#1a1a1a;font-family:'Segoe UI',sans-serif;padding:30px 20px;}}.card{{max-width:1000px;margin:0 auto;background:#2d2d2d;border-radius:32px;overflow:hidden;color:#e0e0e0;}}.header{{background:#3a3a3a;padding:30px 25px;text-align:center;border-bottom:1px solid #555;}}.logo{{font-size:48px;margin-bottom:10px;}}.title{{font-size:28px;font-weight:800;color:#fff;}}.badge{{background:#555;display:inline-block;padding:6px 18px;border-radius:40px;margin-top:15px;}}.content{{padding:30px;}}.section{{background:#3a3a3a;border-radius:24px;margin-bottom:25px;border:1px solid #555;}}.section-title{{background:#444;padding:16px 24px;font-weight:700;font-size:18px;border-bottom:1px solid #555;}}.section-body{{padding:20px 24px;}}.info-row{{display:flex;padding:10px 0;border-bottom:1px solid #555;}}.info-label{{width:150px;font-weight:600;color:#aaa;}}.info-value{{flex:1;color:#ddd;word-break:break-word;}}.person-card{{background:#444;border-radius:20px;padding:18px;margin-bottom:18px;border:1px solid #555;}}.person-name{{font-size:18px;font-weight:700;color:#fff;margin-bottom:14px;padding-bottom:8px;border-bottom:2px solid #666;}}.person-detail{{display:flex;padding:6px 0;font-size:14px;}}.person-icon{{width:32px;color:#aaa;}}.person-label{{width:90px;color:#aaa;}}.person-value{{flex:1;color:#ddd;}}.source-list{{display:flex;flex-wrap:wrap;gap:10px;}}.source-tag{{background:#555;padding:6px 14px;border-radius:30px;font-size:12px;color:#ccc;}}.stats-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:15px;margin-top:10px;}}.stat-card{{background:#444;border-radius:18px;padding:18px;text-align:center;border:1px solid #555;}}.stat-number{{font-size:32px;font-weight:800;color:#fff;}}.stat-label{{font-size:12px;color:#aaa;}}.footer{{background:#222;padding:18px;text-align:center;color:#888;border-top:1px solid #444;}}.footer a{{color:#aaa;text-decoration:none;}}
</style>
</head>
<body>
<div class="card">
    <div class="header"><div class="logo">{'<img src="data:image/png;base64,'+logo+'" style="max-height:70px">' if logo else '🌿'}</div><div class="title">VANILLA SEARCH</div><div class="badge">🔍 {search_type.upper()} · {query}</div></div>
    <div class="content">
        <div class="section"><div class="section-title">📋 ОСНОВНАЯ ИНФОРМАЦИЯ</div><div class="section-body"><div class="info-row"><div class="info-label">Запрос</div><div class="info-value">{query}</div></div><div class="info-row"><div class="info-label">Тип</div><div class="info-value">{search_type.upper()}</div></div><div class="info-row"><div class="info-label">Время</div><div class="info-value">{now}</div></div></div></div>
        <div class="section"><div class="section-title">📡 ДАННЫЕ О НОМЕРЕ</div><div class="section-body"><div class="info-row"><div class="info-label">Номер</div><div class="info-value">{query}</div></div><div class="info-row"><div class="info-label">Оператор</div><div class="info-value">{operator}</div></div><div class="info-row"><div class="info-label">Регион</div><div class="info-value">{region}</div></div><div class="info-row"><div class="info-label">Страна</div><div class="info-value">{country}</div></div></div></div>
        <div class="section"><div class="section-title">👤 ПЕРСОНЫ ({len(persons)})</div><div class="section-body">{persons_html}</div></div>
        <div class="section"><div class="section-title">📚 ИСТОЧНИКИ ({len(sources)})</div><div class="section-body"><div class="source-list">{sources_html}</div></div></div>
        <div class="section"><div class="section-title">📊 СТАТИСТИКА</div><div class="section-body"><div class="stats-grid"><div class="stat-card"><div class="stat-number">{len(persons)}</div><div class="stat-label">ПЕРСОН</div></div><div class="stat-card"><div class="stat-number">{len(sources)}</div><div class="stat-label">ИСТОЧНИКОВ</div></div><div class="stat-card"><div class="stat-number">{now[:10]}</div><div class="stat-label">ДАТА</div></div></div></div></div>
    </div>
    <div class="footer">Vanilla Search · <a href="https://t.me/bothkm">by bothkm.t.me</a><br>⚠️ Все данные выдуманы, совпадения случайны</div>
</div>
</body>
</html>"""

# ---------- API ДЛЯ VK, IP, MAC ----------
def search_vk(q):
    try:
        uid = re.sub(r'(https?://)?(vk\.com/|vkontakte\.ru/|@)', '', q).strip('/')
        url = f"https://api.vk.com/method/users.get?user_ids={uid}&access_token={VK_TOKEN}&v=5.131&fields=first_name,last_name,online"
        r = requests.get(url, timeout=15)
        if r.status_code == 200 and r.json().get('response'):
            u = r.json()['response'][0]
            return f"🐧 *VK*\nID: {u['id']}\nИмя: {u['first_name']} {u['last_name']}\nСтатус: {'Онлайн' if u.get('online') else 'Офлайн'}"
    except:
        pass
    return None

def search_ip(ip):
    try:
        r = requests.get(f"https://api.ipdata.co/{ip}?api-key={IPDATA_KEY}", timeout=10)
        if r.status_code == 200:
            d = r.json()
            return f"🌐 *IP*\nСтрана: {d.get('country_name')}\nГород: {d.get('city')}\nПровайдер: {d.get('asn', {}).get('name')}"
    except:
        pass
    return None

def search_mac(mac):
    try:
        oui = re.sub(r'[:-]', '', mac).upper()[:6]
        r = requests.get(f"https://api.macvendors.com/{oui}", timeout=10)
        if r.status_code == 200:
            return f"🔌 *MAC*\nMAC: {mac.upper()}\nПроизводитель: {r.text.strip()}"
    except:
        pass
    return None

# ---------- ОСНОВНОЙ БОТ ----------
bot = telebot.TeleBot(MAIN_TOKEN)

def check_all_subscriptions(user_id):
    for ch in CHANNELS:
        try:
            status = bot.get_chat_member(ch["username"], user_id).status
            if status not in ['member', 'administrator', 'creator']:
                return False
        except:
            return False
    return True

def main_menu():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🔍 ПОИСК", callback_data="search_menu"),
        types.InlineKeyboardButton("📊 ПРОФИЛЬ", callback_data="profile"),
        types.InlineKeyboardButton("📜 ИСТОРИЯ", callback_data="history"),
        types.InlineKeyboardButton("📊 СТАТИСТИКА", callback_data="stats"),
        types.InlineKeyboardButton("🎭 МАСКИРОВКА", callback_data="buy_mask"),
        types.InlineKeyboardButton("👥 РЕФЕРАЛЫ", callback_data="referral"),
        types.InlineKeyboardButton("❓ ПОМОЩЬ", callback_data="help")
    )
    return kb

def search_type_menu():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("👤 ФИО + дата", callback_data="type_name"),
        types.InlineKeyboardButton("📱 Телефон", callback_data="type_phone"),
        types.InlineKeyboardButton("🏠 Адрес", callback_data="type_address"),
        types.InlineKeyboardButton("📋 СНИЛС", callback_data="type_snils"),
        types.InlineKeyboardButton("🪪 Паспорт", callback_data="type_passport"),
        types.InlineKeyboardButton("🐧 ВКонтакте", callback_data="type_vk"),
        types.InlineKeyboardButton("🌐 IP-адрес", callback_data="type_ip"),
        types.InlineKeyboardButton("🔌 MAC-адрес", callback_data="type_mac"),
        types.InlineKeyboardButton("⬅️ НАЗАД", callback_data="back_to_menu")
    )
    return kb

def admin_menu():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("📊 СТАТИСТИКА", callback_data="admin_stats"),
        types.InlineKeyboardButton("📢 РАССЫЛКА", callback_data="admin_mail"),
        types.InlineKeyboardButton("👥 ПОЛЬЗОВАТЕЛИ", callback_data="admin_users"),
        types.InlineKeyboardButton("🔍 ПОИСКИ ПОЛЬЗОВАТЕЛЯ", callback_data="admin_user_searches"),
        types.InlineKeyboardButton("📝 ОТПРАВИТЬ СООБЩЕНИЕ", callback_data="admin_send_msg"),
        types.InlineKeyboardButton("🚫 БАН/РАЗБАН", callback_data="admin_ban"),
        types.InlineKeyboardButton("💎 ВЫДАТЬ ЗАПРОСЫ", callback_data="admin_add_queries"),
        types.InlineKeyboardButton("💎 ЗАБРАТЬ ЗАПРОСЫ", callback_data="admin_remove_queries"),
        types.InlineKeyboardButton("👑 ВЫДАТЬ ПОДПИСКУ", callback_data="admin_add_subscription"),
        types.InlineKeyboardButton("👑 ЗАБРАТЬ ПОДПИСКУ", callback_data="admin_remove_subscription"),
        types.InlineKeyboardButton("🔙 НАЗАД", callback_data="back_admin")
    )
    return kb

@bot.message_handler(commands=['start'])
def start_cmd(m):
    uid = m.from_user.id
    username = m.from_user.username or ""
    first_name = m.from_user.first_name or ""
    last_name = m.from_user.last_name or ""
    ref = 0
    if len(m.text.split()) > 1:
        try:
            ref = int(m.text.split()[1])
            if ref == uid:
                ref = 0
        except:
            pass
    add_user(uid, username, first_name, last_name, ref)
    if is_banned(uid):
        bot.send_message(uid, "🚫 Вы заблокированы.", protect_content=True)
        return
    if not is_captcha_passed(uid):
        cid, q = generate_captcha()
        msg = bot.send_message(uid, f"🤖 *Каптча*: {q} = ?", parse_mode='Markdown', protect_content=True)
        bot.register_next_step_handler(msg, captcha_step, cid, uid)
        return
    verify_referral(uid)
    if not check_all_subscriptions(uid):
        kb = types.InlineKeyboardMarkup()
        for ch in CHANNELS:
            kb.add(types.InlineKeyboardButton(f"📢 {ch['username']}", url=ch['link']))
        kb.add(types.InlineKeyboardButton("✅ ПОДПИСАЛСЯ", callback_data="check_sub"))
        bot.send_message(uid, "Подпишитесь на все каналы:", reply_markup=kb, protect_content=True)
        return
    free = get_free_searches(uid)
    unlimited = is_unlimited(uid)
    ref_count = get_referral_count(uid)
    welcome = f"""🌿 *Vanilla Search* 🌿

⚠️ *ВСЕ ДАННЫЕ ВЫДУМАНЫ, СОВПАДЕНИЯ СЛУЧАЙНЫ*

🔍 *Доступные типы поиска:*
├ 👤 ФИО + дата рождения
├ 📱 Телефон
├ 🏠 Адрес
├ 📋 СНИЛС
├ 🪪 Паспорт
├ 🐧 ВК
├ 🌐 IP
└ 🔌 MAC

💎 *Ваш статус:*
├ Бесплатных поисков: {free}
├ Бессрочная подписка: {'✅' if unlimited else '❌'}
└ Приглашено друзей: {ref_count}/{REQUIRED_REFERRALS_FOR_UNLIMITED}

👥 *Реферальная ссылка:* `https://t.me/{bot.get_me().username}?start={uid}`

*Vanilla Search - by bothkm.t.me*"""
    bot.send_message(uid, welcome, reply_markup=main_menu(), parse_mode='Markdown', protect_content=True)

def captcha_step(m, cid, uid):
    if check_captcha(cid, m.text.strip()):
        update_captcha(uid)
        bot.send_message(uid, "✅ Каптча пройдена", protect_content=True)
        verify_referral(uid)
        start_cmd(m)
    else:
        bot.send_message(uid, "❌ Ошибка, начните /start", protect_content=True)

@bot.callback_query_handler(func=lambda c: True)
def callback_handler(c):
    uid = c.from_user.id
    if c.data == "check_sub":
        if check_all_subscriptions(uid):
            update_subscription(uid, 1)
            bot.send_message(uid, "✅ Спасибо!", reply_markup=main_menu(), protect_content=True)
        else:
            bot.answer_callback_query(c.id, "❌ Подпишитесь на все каналы", show_alert=True)
    elif c.data == "back_to_menu":
        bot.edit_message_text("🌿 Главное меню", uid, c.message.message_id, reply_markup=main_menu())
    elif c.data == "search_menu":
        bot.edit_message_text("🔍 *Выберите тип поиска:*", uid, c.message.message_id, reply_markup=search_type_menu(), parse_mode='Markdown')
    elif c.data == "profile":
        cnt = get_user_search_count(uid)
        total = get_total_searches()
        today = get_today_searches()
        free = get_free_searches(uid)
        unlimited = "✅" if is_unlimited(uid) else "❌"
        ref_count = get_referral_count(uid)
        txt = f"📊 *Профиль*\nID: {uid}\nВаших поисков: {cnt}\nВсего: {total}\nСегодня: {today}\nБесплатных осталось: {free}\nБессрочно: {unlimited}\nПриглашено друзей: {ref_count}/{REQUIRED_REFERRALS_FOR_UNLIMITED}\n\n*Vanilla Search - by bothkm.t.me*"
        bot.edit_message_text(txt, uid, c.message.message_id, parse_mode='Markdown', reply_markup=main_menu())
    elif c.data == "history":
        hist = get_user_history(uid)
        if not hist:
            txt = "📜 История пуста"
        else:
            txt = "📜 *Последние 20:*\n"
            for q,t,d in hist:
                txt += f"\n• `{q}` ({t})\n  {d[:16]}"
        txt += "\n\n*Vanilla Search - by bothkm.t.me*"
        bot.edit_message_text(txt, uid, c.message.message_id, parse_mode='Markdown', reply_markup=main_menu())
    elif c.data == "stats":
        total = get_total_searches()
        today = get_today_searches()
        txt = f"📊 *Статистика*\nВсего поисков: {total}\nСегодня: {today}\n\n*Vanilla Search - by bothkm.t.me*"
        bot.edit_message_text(txt, uid, c.message.message_id, parse_mode='Markdown', reply_markup=main_menu())
    elif c.data == "referral":
        bot_info = bot.get_me()
        link = f"https://t.me/{bot_info.username}?start={uid}"
        ref_count = get_referral_count(uid)
        txt = f"👥 *Реферальная программа*\n\nВаша ссылка: {link}\nПриглашено друзей: {ref_count}/{REQUIRED_REFERRALS_FOR_UNLIMITED}\n\nЗа каждого друга, прошедшего каптчу, вы получаете +1 к счётчику. Когда наберётся {REQUIRED_REFERRALS_FOR_UNLIMITED} – вы получите **бессрочный доступ** навсегда!\n\n*Vanilla Search - by bothkm.t.me*"
        bot.edit_message_text(txt, uid, c.message.message_id, parse_mode='Markdown', reply_markup=main_menu())
    elif c.data == "buy_mask":
        msg = bot.send_message(uid, "🎭 *Маскировка данных*\n\nВведите номер телефона, который хотите скрыть (в формате +79001234567):\n\nСтоимость: 10 Telegram Stars.", parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_mask_number)
    elif c.data == "help":
        txt = """❓ *Помощь*

⚠️ *ВСЕ ДАННЫЕ ВЫДУМАНЫ, СОВПАДЕНИЯ СЛУЧАЙНЫ*

📌 *Как пользоваться:*
1. Нажмите «🔍 ПОИСК»
2. Выберите тип данных
3. Введите запрос в соответствии с примером
4. Получите результат в виде HTML-файла

💎 *Бесплатные поиски:* 5 штук (даются после подписки на каналы)
🎭 *Маскировка:* 10 Stars – номер полностью скрывается
👥 *Рефералы:* пригласи 5 друзей → бессрочный доступ

*Vanilla Search - by bothkm.t.me*

👨‍💻 *Поддержка:* @bothkm"""
        bot.edit_message_text(txt, uid, c.message.message_id, parse_mode='Markdown', reply_markup=main_menu())
    elif c.data.startswith("type_"):
        search_type = c.data.replace("type_", "")
        prompts = {
            "name": "👤 *Введите ФИО и дату рождения*\nПример: Иванов Иван 01.01.1990",
            "phone": "📱 *Введите номер телефона*\nПример: +79001234567",
            "address": "🏠 *Введите адрес*\nПример: г. Москва, ул. Тверская 1",
            "snils": "📋 *Введите СНИЛС*\nПример: 123-456-789 01",
            "passport": "🪪 *Введите паспорт*\nПример: 4616 233456",
            "vk": "🐧 *Введите ссылку на VK*\nПример: vk.com/durov",
            "ip": "🌐 *Введите IP-адрес*\nПример: 8.8.8.8",
            "mac": "🔌 *Введите MAC-адрес*\nПример: 00:1A:2B:3C:4D:5E"
        }
        bot.edit_message_text(prompts.get(search_type, "Введите данные:"), uid, c.message.message_id, parse_mode='Markdown')
        bot.register_next_step_handler_by_chat_id(uid, lambda msg: process_search(msg, search_type))
    # ----- АДМИН-ПАНЕЛЬ -----
    elif c.data == "admin_stats":
        if uid != ADMIN_ID:
            bot.answer_callback_query(c.id, "⛔ Нет доступа", show_alert=True)
            return
        total = get_total_searches()
        today = get_today_searches()
        bot.send_message(uid, f"📊 Статистика\nВсего поисков: {total}\nСегодня: {today}", protect_content=True)
    elif c.data == "admin_mail":
        if uid != ADMIN_ID:
            bot.answer_callback_query(c.id, "⛔ Нет доступа", show_alert=True)
            return
        msg = bot.send_message(uid, "📢 Введите текст рассылки:", protect_content=True)
        bot.register_next_step_handler(msg, do_mailing)
    elif c.data == "admin_users":
        if uid != ADMIN_ID:
            bot.answer_callback_query(c.id, "⛔ Нет доступа", show_alert=True)
            return
        users = get_all_users(50)
        txt = "👥 Последние 50 пользователей:\n"
        for u in users:
            txt += f"\n🆔 {u[0]} | {u[1] or u[2] or 'no name'} | поисков {u[5]} | {u[4][:10]}"
        bot.send_message(uid, txt[:4000], protect_content=True)
    elif c.data == "admin_user_searches":
        if uid != ADMIN_ID:
            bot.answer_callback_query(c.id, "⛔ Нет доступа", show_alert=True)
            return
        msg = bot.send_message(uid, "🔍 Введите ID пользователя:", protect_content=True)
        bot.register_next_step_handler(msg, show_user_searches)
    elif c.data == "admin_send_msg":
        if uid != ADMIN_ID:
            bot.answer_callback_query(c.id, "⛔ Нет доступа", show_alert=True)
            return
        msg = bot.send_message(uid, "📝 Формат: ID текст\nПример: 123456789 Привет", protect_content=True)
        bot.register_next_step_handler(msg, send_to_user)
    elif c.data == "admin_ban":
        if uid != ADMIN_ID:
            bot.answer_callback_query(c.id, "⛔ Нет доступа", show_alert=True)
            return
        msg = bot.send_message(uid, "🚫 Введите ID для бана/разбана:", protect_content=True)
        bot.register_next_step_handler(msg, toggle_ban)
    elif c.data == "admin_add_queries":
        if uid != ADMIN_ID:
            bot.answer_callback_query(c.id, "⛔ Нет доступа", show_alert=True)
            return
        msg = bot.send_message(uid, "💎 *Выдать запросы*\n\nВведите ID и количество через пробел:\nПример: `123456789 10`", parse_mode='Markdown', protect_content=True)
        bot.register_next_step_handler(msg, admin_add_queries_step)
    elif c.data == "admin_remove_queries":
        if uid != ADMIN_ID:
            bot.answer_callback_query(c.id, "⛔ Нет доступа", show_alert=True)
            return
        msg = bot.send_message(uid, "💎 *Забрать запросы*\n\nВведите ID и количество через пробел:\nПример: `123456789 5`", parse_mode='Markdown', protect_content=True)
        bot.register_next_step_handler(msg, admin_remove_queries_step)
    elif c.data == "admin_add_subscription":
        if uid != ADMIN_ID:
            bot.answer_callback_query(c.id, "⛔ Нет доступа", show_alert=True)
            return
        msg = bot.send_message(uid, "👑 *Выдать подписку*\n\nВведите ID и количество дней (0 = бессрочно):\nПример: `123456789 30` или `123456789 0`", parse_mode='Markdown', protect_content=True)
        bot.register_next_step_handler(msg, admin_add_subscription_step)
    elif c.data == "admin_remove_subscription":
        if uid != ADMIN_ID:
            bot.answer_callback_query(c.id, "⛔ Нет доступа", show_alert=True)
            return
        msg = bot.send_message(uid, "👑 *Забрать подписку*\n\nВведите ID пользователя:\nПример: `123456789`", parse_mode='Markdown', protect_content=True)
        bot.register_next_step_handler(msg, admin_remove_subscription_step)
    elif c.data == "back_admin":
        bot.edit_message_text("🔧 Админ-панель", uid, c.message.message_id, reply_markup=admin_menu())

def process_mask_number(m):
    uid = m.from_user.id
    phone = m.text.strip()
    if not re.match(r'^\+?\d{10,12}$', re.sub(r'\D', '', phone)):
        bot.send_message(uid, "❌ Неверный формат номера. Пример: +79001234567", protect_content=True)
        return
    try:
        bot.send_invoice(
            chat_id=uid,
            title="Маскировка номера",
            description=f"Скрытие данных для номера {phone} в HTML-отчётах",
            invoice_payload=f"mask_{phone}",
            provider_token="",
            currency="XTR",
            prices=[types.LabeledPrice(label="Маскировка", amount=STARS_PRICE)],
            start_parameter="mask_subscription",
            need_name=False,
            need_phone_number=False,
            need_email=False
        )
    except Exception as e:
        bot.send_message(uid, f"❌ Ошибка: {e}", protect_content=True)

@bot.pre_checkout_query_handler(func=lambda query: True)
def pre_checkout(query):
    bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def got_payment(m):
    uid = m.from_user.id
    payload = m.successful_payment.invoice_payload
    if payload.startswith("mask_"):
        phone = payload.replace("mask_", "")
        add_masked_number(uid, phone)
        bot.send_message(uid, f"✅ Маскировка для номера {phone} активирована! При поиске этого номера все данные будут скрыты.", protect_content=True)
        send_log(uid, m.from_user.username or "нет_username", phone, "mask", "купил маскировку")
    else:
        bot.send_message(uid, "❌ Неизвестный платёж", protect_content=True)

# ---------- АДМИН-ФУНКЦИИ (шаги) ----------
def admin_add_queries_step(m):
    uid = m.from_user.id
    if uid != ADMIN_ID:
        return
    try:
        parts = m.text.split()
        target_id = int(parts[0])
        amount = int(parts[1])
        add_free_searches(target_id, amount)
        bot.send_message(uid, f"✅ Добавлено {amount} запросов пользователю {target_id}", protect_content=True)
        send_log(target_id, "admin", f"админ выдал {amount} запросов", "admin_action")
    except:
        bot.send_message(uid, "❌ Неверный формат. Пример: 123456789 10", protect_content=True)

def admin_remove_queries_step(m):
    uid = m.from_user.id
    if uid != ADMIN_ID:
        return
    try:
        parts = m.text.split()
        target_id = int(parts[0])
        amount = int(parts[1])
        remove_free_searches(target_id, amount)
        bot.send_message(uid, f"✅ Удалено {amount} запросов у пользователя {target_id}", protect_content=True)
        send_log(target_id, "admin", f"админ забрал {amount} запросов", "admin_action")
    except:
        bot.send_message(uid, "❌ Неверный формат. Пример: 123456789 5", protect_content=True)

def admin_add_subscription_step(m):
    uid = m.from_user.id
    if uid != ADMIN_ID:
        return
    try:
        parts = m.text.split()
        target_id = int(parts[0])
        days = int(parts[1])
        add_subscription_days(target_id, days)
        if days == 0:
            bot.send_message(uid, f"✅ Пользователю {target_id} выдана БЕССРОЧНАЯ подписка", protect_content=True)
        else:
            bot.send_message(uid, f"✅ Пользователю {target_id} выдана подписка на {days} дней", protect_content=True)
        send_log(target_id, "admin", f"админ выдал подписку на {days} дней", "admin_action")
    except:
        bot.send_message(uid, "❌ Неверный формат. Пример: 123456789 30", protect_content=True)

def admin_remove_subscription_step(m):
    uid = m.from_user.id
    if uid != ADMIN_ID:
        return
    try:
        target_id = int(m.text.strip())
        remove_subscription(target_id)
        bot.send_message(uid, f"✅ У пользователя {target_id} удалена подписка (возвращены бесплатные поиски)", protect_content=True)
        send_log(target_id, "admin", f"админ удалил подписку", "admin_action")
    except:
        bot.send_message(uid, "❌ Неверный формат. Пример: 123456789", protect_content=True)

def do_mailing(m):
    uid = m.from_user.id
    if uid != ADMIN_ID:
        return
    text = m.text
    users = get_all_user_ids()
    sent = 0
    for uid_user in users:
        try:
            bot.send_message(uid_user, f"📢 *РАССЫЛКА*\n\n{text}\n\n*Vanilla Search - by bothkm.t.me*", parse_mode='Markdown', protect_content=True)
            sent += 1
            time.sleep(0.05)
        except:
            pass
    bot.send_message(ADMIN_ID, f"✅ Рассылка завершена, отправлено {sent}", protect_content=True)

def show_user_searches(m):
    uid = m.from_user.id
    if uid != ADMIN_ID:
        return
    try:
        target_id = int(m.text.strip())
        hist = get_user_history(target_id)
        if not hist:
            txt = f"У пользователя {target_id} нет поисков"
        else:
            txt = f"🔍 Поиски {target_id}:\n"
            for q,t,d in hist[:20]:
                txt += f"\n• {q} ({t})\n  {d[:16]}"
        bot.send_message(ADMIN_ID, txt[:4000], protect_content=True)
    except:
        bot.send_message(ADMIN_ID, "❌ Неверный ID", protect_content=True)

def send_to_user(m):
    uid = m.from_user.id
    if uid != ADMIN_ID:
        return
    try:
        parts = m.text.split(maxsplit=1)
        target_id = int(parts[0])
        msg_text = parts[1]
        bot.send_message(target_id, f"📝 *Сообщение от администратора:*\n{msg_text}\n\n*Vanilla Search - by bothkm.t.me*", parse_mode='Markdown', protect_content=True)
        bot.send_message(ADMIN_ID, f"✅ Отправлено {target_id}", protect_content=True)
    except:
        bot.send_message(ADMIN_ID, "❌ Ошибка формата. Пример: 123456789 Текст", protect_content=True)

def toggle_ban(m):
    uid = m.from_user.id
    if uid != ADMIN_ID:
        return
    try:
        target_id = int(m.text.strip())
        cur = is_banned(target_id)
        ban_user(target_id, 0 if cur else 1)
        bot.send_message(ADMIN_ID, f"✅ Пользователь {target_id} {'РАЗБАНЕН' if cur else 'ЗАБАНЕН'}", protect_content=True)
    except:
        bot.send_message(ADMIN_ID, "❌ Неверный ID", protect_content=True)

# ---------- АНИМАЦИЯ ПОИСКА ----------
def animated_search(user_id, query, search_type, data_func, masked=False):
    msg = bot.send_message(user_id, "🔍 Поиск", protect_content=True)
    frames = ["🔍 Поиск   ", "🔍 Поиск.  ", "🔍 Поиск.. ", "🔍 Поиск..."]
    for i in range(8):
        time.sleep(0.3)
        try:
            bot.edit_message_text(frames[i % len(frames)], user_id, msg.message_id)
        except:
            pass
    # Выполняем поиск
    if search_type in ("name", "phone", "address", "snils", "passport"):
        data = data_func(query)
        if data:
            html = generate_html_report(query, data, search_type, masked=masked)
            path = f"report_{user_id}_{int(time.time())}.html"
            with open(path, 'w', encoding='utf-8') as f:
                f.write(html)
            with open(path, 'rb') as f:
                bot.send_document(user_id, f, caption=f"✅ HTML-отчёт по запросу: {query}", protect_content=True)
            os.remove(path)
            inc_search(user_id)
            add_search_history(user_id, query, search_type, html[:2000])
            result_text = "✅ Отчёт готов"
        else:
            result_text = "❌ Ничего не найдено"
    else:
        # VK, IP, MAC
        res = data_func(query)
        result_text = res or "❌ Не найдено"
        if res:
            inc_search(user_id)
            add_search_history(user_id, query, search_type, res[:2000])
    try:
        bot.delete_message(user_id, msg.message_id)
    except:
        pass
    bot.send_message(user_id, result_text, parse_mode='Markdown', protect_content=True)

def process_search(m, search_type):
    uid = m.from_user.id
    query = m.text.strip()
    if not query:
        bot.send_message(uid, "❌ Пустой запрос", reply_markup=search_type_menu(), protect_content=True)
        return
    send_log(uid, m.from_user.username or "нет_username", query, search_type)
    if not can_search(uid):
        bot.send_message(uid, "❌ У вас закончились бесплатные поиски!\n\n👥 Пригласите 5 друзей (ваша ссылка в меню «РЕФЕРАЛЫ») – получите бессрочный доступ.", reply_markup=main_menu(), protect_content=True)
        return
    if not has_active_subscription(uid) and not is_unlimited(uid) and uid != ADMIN_ID:
        decrement_free_search(uid)
    if search_type in ("name", "phone", "address", "snils", "passport"):
        masked = is_number_masked(query) if search_type == "phone" else False
        animated_search(uid, query, search_type, lambda q: search_bigbase(q), masked)
    elif search_type == "vk":
        animated_search(uid, query, search_type, lambda q: search_vk(q), False)
    elif search_type == "ip":
        animated_search(uid, query, search_type, lambda q: search_ip(q), False)
    elif search_type == "mac":
        animated_search(uid, query, search_type, lambda q: search_mac(q), False)
    else:
        bot.send_message(uid, "❌ Неизвестный тип", reply_markup=search_type_menu(), protect_content=True)

# ---------- АДМИН-ПАНЕЛЬ (отдельное меню) ----------
@bot.message_handler(commands=['admin'])
def admin_panel_cmd(m):
    if m.from_user.id != ADMIN_ID:
        bot.send_message(m.chat.id, "⛔ Нет доступа", protect_content=True)
        return
    bot.send_message(m.chat.id, "🔧 *АДМИН-ПАНЕЛЬ*", reply_markup=admin_menu(), parse_mode='Markdown', protect_content=True)

# ---------- СТАРТ ----------
if __name__ == "__main__":
    init_db()
    try:
        bot.send_message(LOG_CHANNEL, "🌿 Бот Vanilla Search запущен", protect_content=True)
    except:
        pass
    print("🌿 Основной бот запущен")
    while True:
        try:
            bot.infinity_polling(timeout=30)
        except Exception as e:
            print(f"Ошибка: {e}")
            time.sleep(3)