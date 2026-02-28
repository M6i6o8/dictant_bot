import json
import random
import os
import requests
import hashlib
import re
from datetime import datetime

# Новая библиотека Gemini
try:
    from google import genai
    GEMINI_AVAILABLE = True
    print("✅ Новая Gemini библиотека загружена")
except ImportError:
    GEMINI_AVAILABLE = False
    print("⚠️ Gemini библиотека не установлена, нужно: pip install google-genai")

# ===== НАСТРОЙКИ =====
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
SENTENCES_FILE = 'sentences.json'
USED_SENTENCES_FILE = 'used_sentences.txt'
LAST_SENTENCE_FILE = 'last_sentence.json'

OPENROUTER_KEY = os.environ.get('OPENROUTER_KEY')
GEMINI_KEY = os.environ.get('GEMINI_KEY')
CEREBRAS_KEY = os.environ.get('CEREBRAS_KEY')

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
CEREBRAS_URL = "https://api.cerebras.ai/v1/chat/completions"

# Тип запуска определяем по минутам
current_minute = datetime.now().minute
RUN_TYPE = 'answer' if 10 <= current_minute < 20 else 'task'
print(f"📌 Тип запуска: {RUN_TYPE} (по минуте {current_minute})")

# ===== УНИВЕРСАЛЬНЫЙ ИЗВЛЕКАТЕЛЬ JSON =====
def extract_json(text):
    """Универсально извлекает JSON из любого текста"""
    if not text:
        return None
    
    text = text.replace('```json', '').replace('```', '').replace('`', '').strip()
    json_pattern = r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}'
    matches = re.findall(json_pattern, text)
    
    for json_str in matches:
        for attempt in [
            json_str,
            json_str.replace("'", '"'),
            json_str.replace('\n', ' ').replace('\r', ''),
            re.sub(r',\s*}', '}', json_str)
        ]:
            try:
                data = json.loads(attempt)
                if isinstance(data, dict):
                    return data
            except:
                continue
    return None

# ===== ФУНКЦИИ РАБОТЫ С БАЗОЙ =====
def load_sentences():
    try:
        with open(SENTENCES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data['sentences']
    except:
        return [
            {"id": 1, "en": "I like to read books", "ru": "Я люблю читать книги", "topic": "📚 Хобби", "difficulty": "легко", "explanation": "Present Simple для привычки."},
            {"id": 2, "en": "She works as a doctor", "ru": "Она работает врачом", "topic": "💼 Работа", "difficulty": "легко", "explanation": "Present Simple, после she добавляем -s."},
        ]

def load_used_ids():
    try:
        if os.path.exists(USED_SENTENCES_FILE):
            with open(USED_SENTENCES_FILE, 'r') as f:
                return set(map(int, f.read().strip().split(','))) if f.read().strip() else set()
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

def is_used(sentence):
    used_ids = load_used_ids()
    if 'id' in sentence:
        return sentence['id'] in used_ids
    text_hash = hashlib.md5(sentence['en'].encode()).hexdigest()[:8]
    fake_id = int(text_hash, 16) % 1000000
    return fake_id in used_ids

# ===== СОХРАНЕНИЕ ПОСЛЕДНЕГО ПРЕДЛОЖЕНИЯ =====
def save_last_sentence(sentence):
    with open(LAST_SENTENCE_FILE, 'w', encoding='utf-8') as f:
        json.dump(sentence, f, ensure_ascii=False, indent=2)
    print("✅ Последнее предложение сохранено")

def load_last_sentence():
    if os.path.exists(LAST_SENTENCE_FILE):
        with open(LAST_SENTENCE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

# ===== ГЕНЕРАЦИЯ =====
def generate_with_gemini():
    if not GEMINI_AVAILABLE or not GEMINI_KEY:
        return None
    try:
        client = genai.Client(api_key=GEMINI_KEY)
        prompt = """Ты преподаватель английского. Сгенерируй предложение с разбором.
        Верни ТОЛЬКО JSON:
        {"en": "...", "ru": "...", "topic": "...", "difficulty": "легко/средне", "explanation": "..."}"""
        response = client.models.generate_content(model='models/gemini-1.5-flash', contents=prompt)
        return extract_json(response.text)
    except Exception as e:
        print(f"⚠️ Gemini ошибка: {type(e).__name__}")
        return None

def generate_with_cerebras():
    if not CEREBRAS_KEY:
        return None
    try:
        response = requests.post(
            CEREBRAS_URL,
            headers={"Authorization": f"Bearer {CEREBRAS_KEY}"},
            json={
                "model": "llama3.3-70b",
                "messages": [{"role": "user", "content": "Создай JSON с en, ru, topic, explanation"}],
                "temperature": 0.8
            },
            timeout=20
        )
        if response.status_code == 200:
            return extract_json(response.json()['choices'][0]['message']['content'])
    except:
        return None

def generate_with_openrouter():
    if not OPENROUTER_KEY:
        return None
    try:
        response = requests.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {OPENROUTER_KEY}"},
            json={
                "model": "openrouter/free",
                "messages": [{"role": "user", "content": "Создай JSON с en, ru, topic, explanation"}]
            },
            timeout=20
        )
        if response.status_code == 200:
            return extract_json(response.json()['choices'][0]['message']['content'])
    except:
        return None

def get_unique_ai_sentence():
    providers = [
        ("Gemini", generate_with_gemini),
        ("Cerebras", generate_with_cerebras),
        ("OpenRouter", generate_with_openrouter)
    ]
    for name, func in providers:
        print(f"🤖 Пробую {name}...")
        sentence = func()
        if sentence and not is_used(sentence) and all(k in sentence for k in ['en','ru','topic','explanation']):
            print(f"✅ {name} сработал!")
            return sentence
    return None

def get_unique_db_sentence():
    sentences = load_sentences()
    used = load_used_ids()
    available = [s for s in sentences if s['id'] not in used]
    if not available:
        save_used_ids(set())
        available = sentences
    return random.choice(available)

def send_telegram_message(text):
    if not BOT_TOKEN or not CHAT_ID:
        return None
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={'chat_id': CHAT_ID, 'text': text, 'parse_mode': 'HTML'},
            timeout=10
        )
        if r.status_code == 200 and r.json().get('ok'):
            print("✅ Сообщение отправлено")
            return True
    except:
        pass
    return False

def main():
    print("\n" + "="*60)
    print("🚀 ЗАПУСК БОТА")
    print("="*60)
    
    print(f"🤖 Gemini: {'✅' if GEMINI_KEY else '❌'}")
    print(f"🤖 Cerebras: {'✅' if CEREBRAS_KEY else '❌'}")
    print(f"🤖 OpenRouter: {'✅' if OPENROUTER_KEY else '❌'}")
    
    # Логика: в task генерируем и сохраняем, в answer загружаем
    if RUN_TYPE == 'task':
        print("\n🔍 ГЕНЕРИРУЕМ НОВОЕ...")
        sentence = get_unique_ai_sentence()
        if not sentence:
            sentence = get_unique_db_sentence()
        if not sentence:
            print("❌ Нет предложения")
            return
        
        save_last_sentence(sentence)
        mark_as_used(sentence)
        
        msg = f"📝 <b>ЕЖЕДНЕВНЫЙ ДИКТАНТ</b>\n\n"
        msg += f"<b>Тема:</b> {sentence['topic']}\n"
        msg += f"<b>Сложность:</b> {sentence.get('difficulty', 'легко')}\n\n"
        msg += f"🇬🇧 <b>Переведи на русский:</b>\n"
        msg += f"<i>{sentence['en']}</i>\n\n"
        msg += f"⏳ <b>Ответ и разбор придут через 10 минут</b>"
        
        print("\n📨 Отправляем ЗАДАНИЕ...")
        
    else:  # answer
        print("\n🔍 ЗАГРУЖАЕМ СОХРАНЕННОЕ...")
        sentence = load_last_sentence()
        if not sentence:
            print("⚠️ Нет сохранённого, генерируем новое...")
            sentence = get_unique_ai_sentence() or get_unique_db_sentence()
            if not sentence:
                print("❌ Нет предложения")
                return
        
        msg = f"📝 <b>ПРОВЕРКА ДИКТАНТА</b>\n\n"
        msg += f"🇬🇧 <b>Было:</b> {sentence['en']}\n"
        msg += f"🇷🇺 <b>Правильный перевод:</b>\n"
        msg += f"<i>{sentence['ru']}</i>\n\n"
        msg += f"📊 <b>Грамматический разбор:</b>\n"
        msg += f"{sentence.get('explanation', 'Молодец!')}\n\n"
        msg += f"💪 Отличной работы!"
        
        print("\n📨 Отправляем ОТВЕТ...")
    
    if send_telegram_message(msg):
        print("\n✅ ВСЁ ГОТОВО")
    else:
        print("\n❌ Ошибка отправки")
    print("="*60)

if __name__ == "__main__":
    main()
