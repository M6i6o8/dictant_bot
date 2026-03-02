import json
import random
import os
import requests
import hashlib
import re
from datetime import datetime

# Google Gemini
try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# ===== НАСТРОЙКИ =====
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
SENTENCES_FILE = 'sentences.json'
USED_SENTENCES_FILE = 'used_sentences.txt'
LAST_SENTENCE_FILE = 'last_sentence.json'
ANSWER_SENT_FILE = 'answer_sent.txt'

OPENROUTER_KEY = os.environ.get('OPENROUTER_KEY')
GEMINI_KEY = os.environ.get('GEMINI_KEY')
CEREBRAS_KEY = os.environ.get('CEREBRAS_KEY')

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
CEREBRAS_URL = "https://api.cerebras.ai/v1/chat/completions"

# ===== НАСТРОЙКА ВРЕМЕНИ =====
TASK_HOUR_MSK = 13
TASK_MINUTE_MSK = 31
ANSWER_HOUR_MSK = 13
ANSWER_MINUTE_MSK = 50

TASK_HOUR_UTC = TASK_HOUR_MSK - 3
ANSWER_HOUR_UTC = ANSWER_HOUR_MSK - 3

if TASK_HOUR_UTC < 0:
    TASK_HOUR_UTC += 24
if ANSWER_HOUR_UTC < 0:
    ANSWER_HOUR_UTC += 24

print(f"\n⚙️ ЗАДАНИЕ: {TASK_HOUR_MSK:02d}:{TASK_MINUTE_MSK:02d} МСК = {TASK_HOUR_UTC:02d}:{TASK_MINUTE_MSK:02d} UTC")
print(f"⚙️ ОТВЕТ:   {ANSWER_HOUR_MSK:02d}:{ANSWER_MINUTE_MSK:02d} МСК = {ANSWER_HOUR_UTC:02d}:{ANSWER_MINUTE_MSK:02d} UTC")

# ===== ПРОВЕРКА НАЛИЧИЯ ФАЙЛОВ =====
print(f"\n📁 Проверка файлов перед запуском:")
print(f"   last_sentence.json: {'✅' if os.path.exists(LAST_SENTENCE_FILE) else '❌'}")
print(f"   used_sentences.txt: {'✅' if os.path.exists(USED_SENTENCES_FILE) else '❌'}")
print(f"   answer_sent.txt: {'✅' if os.path.exists(ANSWER_SENT_FILE) else '❌'}")

# ===== ОПРЕДЕЛЕНИЕ ТИПА ЗАПУСКА =====
def get_run_type():
    current_hour = datetime.now().hour
    current_minute = datetime.now().minute
    
    print(f"\n🕐 UTC: {current_hour}:{current_minute:02d}")
    print(f"🕐 МСК: {current_hour+3}:{current_minute:02d}")
    
    # Задание: 30 минут после TASK_HOUR_UTC
    if current_hour == TASK_HOUR_UTC and TASK_MINUTE_MSK <= current_minute < TASK_MINUTE_MSK + 30:
        return 'task'
    
    # Ответ: 30 минут после ANSWER_HOUR_UTC
    if current_hour == ANSWER_HOUR_UTC and ANSWER_MINUTE_MSK <= current_minute < ANSWER_MINUTE_MSK + 30:
        return 'answer'
    
    return 'idle'

RUN_TYPE = get_run_type()
print(f"📌 Режим: {RUN_TYPE}")

# ===== ФУНКЦИИ =====
def extract_json(text):
    if not text:
        return None
    text = text.replace('```json', '').replace('```', '').strip()
    json_pattern = r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}'
    matches = re.findall(json_pattern, text)
    for json_str in matches:
        try:
            return json.loads(json_str)
        except:
            try:
                return json.loads(json_str.replace("'", '"'))
            except:
                continue
    return None

def load_used_ids():
    try:
        if os.path.exists(USED_SENTENCES_FILE):
            with open(USED_SENTENCES_FILE, 'r') as f:
                content = f.read().strip()
                return set(map(int, content.split(','))) if content else set()
    except:
        pass
    return set()

def save_used_ids(used_ids):
    with open(USED_SENTENCES_FILE, 'w') as f:
        f.write(','.join(map(str, used_ids)))

def mark_as_used(sentence):
    used_ids = load_used_ids()
    if 'id' not in sentence:
        text_hash = hashlib.md5(sentence['en'].encode()).hexdigest()[:8]
        sentence['id'] = int(text_hash, 16) % 1000000
    used_ids.add(sentence['id'])
    save_used_ids(used_ids)
    print(f"✅ ID {sentence['id']} добавлен в used_sentences.txt")

def is_used(sentence):
    used_ids = load_used_ids()
    if 'id' in sentence:
        return sentence['id'] in used_ids
    return False

def save_last_sentence(sentence):
    try:
        with open(LAST_SENTENCE_FILE, 'w', encoding='utf-8') as f:
            json.dump(sentence, f, ensure_ascii=False)
        print(f"✅ Предложение сохранено в {LAST_SENTENCE_FILE}")
        return True
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")
        return False

def load_last_sentence():
    try:
        if os.path.exists(LAST_SENTENCE_FILE):
            with open(LAST_SENTENCE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"❌ Ошибка загрузки: {e}")
    return None

def was_task_sent_today():
    return os.path.exists(LAST_SENTENCE_FILE)

def is_answer_sent_today():
    if os.path.exists(ANSWER_SENT_FILE):
        with open(ANSWER_SENT_FILE, 'r') as f:
            return f.read().strip() == datetime.now().strftime('%Y-%m-%d')
    return False

def mark_answer_sent():
    with open(ANSWER_SENT_FILE, 'w') as f:
        f.write(datetime.now().strftime('%Y-%m-%d'))

def generate_with_gemini():
    if not GEMINI_AVAILABLE or not GEMINI_KEY:
        return None
    try:
        client = genai.Client(api_key=GEMINI_KEY)
        prompt = """Создай JSON для изучения английского:
        {"en": "...", "ru": "...", "topic": "...", "explanation": "..."}"""
        response = client.models.generate_content(
            model='models/gemini-1.5-flash',
            contents=prompt
        )
        return extract_json(response.text)
    except:
        return None

def generate_with_cerebras():
    if not CEREBRAS_KEY:
        return None
    try:
        r = requests.post(CEREBRAS_URL, 
            headers={"Authorization": f"Bearer {CEREBRAS_KEY}"},
            json={"model": "llama3.3-70b", "messages": [{"role": "user", "content": "JSON с en, ru, topic"}]},
            timeout=15)
        return extract_json(r.json()['choices'][0]['message']['content']) if r.status_code == 200 else None
    except:
        return None

def generate_with_openrouter():
    if not OPENROUTER_KEY:
        return None
    try:
        r = requests.post(OPENROUTER_URL,
            headers={"Authorization": f"Bearer {OPENROUTER_KEY}"},
            json={"model": "openrouter/free", "messages": [{"role": "user", "content": "JSON с en, ru, topic"}]},
            timeout=15)
        return extract_json(r.json()['choices'][0]['message']['content']) if r.status_code == 200 else None
    except:
        return None

def get_unique_sentence():
    providers = [generate_with_gemini, generate_with_cerebras, generate_with_openrouter]
    for func in providers:
        s = func()
        if s and all(k in s for k in ['en', 'ru', 'topic']):
            if not is_used(s):
                return s
    return None

def send_telegram_message(text):
    try:
        r = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={'chat_id': CHAT_ID, 'text': text, 'parse_mode': 'HTML'},
            timeout=10)
        return r.status_code == 200 and r.json().get('ok')
    except:
        return False

# ===== ГЛАВНАЯ =====
def main():
    print("\n" + "="*50)
    
    if RUN_TYPE == 'idle':
        print("⏰ Не время")
        return
    
    if RUN_TYPE == 'task':
        print("\n🔍 Генерирую задание...")
        s = get_unique_sentence()
        if not s:
            print("❌ Нет предложения")
            return
        
        save_last_sentence(s)
        mark_as_used(s)
        
        msg = f"📝 <b>ЕЖЕДНЕВНЫЙ ДИКТАНТ</b>\n\n"
        msg += f"<b>Тема:</b> {s['topic']}\n"
        msg += f"🇬🇧 <b>Переведи:</b>\n<i>{s['en']}</i>\n\n"
        msg += f"⏳ <b>Ответ в {ANSWER_HOUR_MSK:02d}:{ANSWER_MINUTE_MSK:02d}</b>"
        
        if send_telegram_message(msg):
            print("✅ Задание отправлено")
        else:
            print("❌ Ошибка")
    
    else:  # answer
        if not was_task_sent_today():
            print("❌ Нет задания")
            return
        
        if is_answer_sent_today():
            print("✅ Ответ уже был")
            return
        
        s = load_last_sentence()
        if not s:
            print("❌ Ошибка загрузки")
            return
        
        expl = s.get('explanation', 'Продолжай практиковаться!')
        
        msg = f"📝 <b>ПРОВЕРКА</b>\n\n"
        msg += f"🇬🇧 <b>Было:</b> {s['en']}\n"
        msg += f"🇷🇺 <b>Перевод:</b> {s['ru']}\n\n"
        msg += f"📊 <b>Разбор:</b>\n{expl}"
        
        if send_telegram_message(msg):
            mark_answer_sent()
            print("✅ Ответ отправлен")
        else:
            print("❌ Ошибка")
    
    print("="*50)

if __name__ == "__main__":
    main()




