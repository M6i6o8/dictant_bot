import json
import random
import os
import requests
import time
import hashlib
import re
from datetime import datetime

# ===== ПОПЫТКА ИМПОРТА GEMINI =====
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
    print("✅ Gemini библиотека загружена")
except ImportError:
    GEMINI_AVAILABLE = False
    print("⚠️ Gemini библиотека не установлена")

# ===== НАСТРОЙКИ =====
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
SENTENCES_FILE = 'sentences.json'
USED_SENTENCES_FILE = 'used_sentences.txt'

# API ключи
OPENROUTER_KEY = os.environ.get('OPENROUTER_KEY')
GEMINI_KEY = os.environ.get('GEMINI_KEY')
CEREBRAS_KEY = os.environ.get('CEREBRAS_KEY')

# URL-ы API
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
CEREBRAS_URL = "https://api.cerebras.ai/v1/chat/completions"

# ===== УНИВЕРСАЛЬНЫЙ ИЗВЛЕКАТЕЛЬ JSON =====
def extract_json(text):
    """Универсально извлекает JSON из любого текста"""
    if not text:
        return None
    
    # Убираем markdown-форматирование
    text = text.replace('```json', '').replace('```', '').replace('`', '').strip()
    
    # Паттерн для поиска JSON объекта
    json_pattern = r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}'
    matches = re.findall(json_pattern, text)
    
    for json_str in matches:
        # Пробуем разные способы парсинга
        for attempt in [
            json_str,  # как есть
            json_str.replace("'", '"'),  # одинарные кавычки -> двойные
            json_str.replace('\n', ' ').replace('\r', ''),  # убираем переносы
            re.sub(r',\s*}', '}', json_str)  # убираем лишние запятые в конце
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
    """Загружает предложения из JSON"""
    try:
        with open(SENTENCES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data['sentences']
    except Exception as e:
        print(f"⚠️ Ошибка загрузки sentences.json: {e}")
        return [
            {"id": 1, "en": "I like to read books", "ru": "Я люблю читать книги", "topic": "📚 Хобби", "difficulty": "легко"},
            {"id": 2, "en": "She works as a doctor", "ru": "Она работает врачом", "topic": "💼 Работа", "difficulty": "легко"},
            {"id": 3, "en": "They are playing football", "ru": "Они играют в футбол", "topic": "⚽ Спорт", "difficulty": "легко"}
        ]

def load_used_ids():
    """Загружает список использованных ID"""
    try:
        if os.path.exists(USED_SENTENCES_FILE):
            with open(USED_SENTENCES_FILE, 'r') as f:
                content = f.read().strip()
                if content:
                    return set(map(int, content.split(',')))
        return set()
    except Exception as e:
        print(f"⚠️ Ошибка чтения использованных ID: {e}")
        return set()

def save_used_ids(used_ids):
    """Сохраняет список использованных ID"""
    try:
        with open(USED_SENTENCES_FILE, 'w') as f:
            f.write(','.join(map(str, used_ids)))
        print(f"✅ Сохранено {len(used_ids)} использованных ID")
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")

def mark_as_used(sentence):
    """Помечает предложение как использованное"""
    used_ids = load_used_ids()
    
    if 'id' not in sentence:
        text_hash = hashlib.md5(sentence['en'].encode()).hexdigest()[:8]
        sentence['id'] = int(text_hash, 16) % 1000000
    
    used_ids.add(sentence['id'])
    save_used_ids(used_ids)
    print(f"📝 Предложение помечено как использованное (ID: {sentence['id']})")
    return sentence['id']

def is_used(sentence):
    """Проверяет, использовалось ли предложение"""
    used_ids = load_used_ids()
    
    if 'id' in sentence:
        return sentence['id'] in used_ids
    
    text_hash = hashlib.md5(sentence['en'].encode()).hexdigest()[:8]
    fake_id = int(text_hash, 16) % 1000000
    return fake_id in used_ids

# ===== ФУНКЦИИ ГЕНЕРАЦИИ =====
def generate_with_openrouter():
    """Генерация через OpenRouter"""
    if not OPENROUTER_KEY:
        return None
    
    models = [
        "openrouter/free",
        "arcee-ai/trinity-large-preview:free",
        "z-ai/glm-4.5-air:free"
    ]
    
    model = random.choice(models)
    
    prompt = """Сгенерируй простое предложение на английском с переводом на русский.
    Верни ТОЛЬКО JSON:
    {
        "en": "предложение на английском",
        "ru": "перевод на русский",
        "topic": "тема с эмодзи",
        "difficulty": "легко"
    }"""
    
    try:
        response = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.8,
                "max_tokens": 200
            },
            timeout=20
        )
        
        if response.status_code == 200:
            result = response.json()
            generated = result['choices'][0]['message']['content']
            print(f"📝 OpenRouter ответ: {generated[:100]}...")
            
            sentence = extract_json(generated)
            if sentence and all(field in sentence for field in ['en', 'ru', 'topic']):
                return sentence
    except Exception as e:
        print(f"⚠️ OpenRouter ошибка: {type(e).__name__}")
    
    return None

def generate_with_cerebras():
    """Генерация через Cerebras"""
    if not CEREBRAS_KEY:
        return None
    
    models = ["llama3.1-8b", "llama3.3-70b"]
    model = random.choice(models)
    
    prompt = """Сгенерируй простое предложение на английском с переводом на русский.
    Верни ТОЛЬКО JSON:
    {"en": "предложение", "ru": "перевод", "topic": "тема", "difficulty": "легко"}"""
    
    try:
        response = requests.post(
            CEREBRAS_URL,
            headers={
                "Authorization": f"Bearer {CEREBRAS_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.8,
                "max_tokens": 150
            },
            timeout=20
        )
        
        if response.status_code == 200:
            result = response.json()
            generated = result['choices'][0]['message']['content']
            print(f"📝 Cerebras ответ: {generated[:100]}...")
            
            sentence = extract_json(generated)
            if sentence and all(field in sentence for field in ['en', 'ru', 'topic']):
                return sentence
    except Exception as e:
        print(f"⚠️ Cerebras ошибка: {type(e).__name__}")
    
    return None

def generate_with_gemini():
    """Генерация через Google Gemini"""
    if not GEMINI_AVAILABLE or not GEMINI_KEY:
        return None
    
    try:
        genai.configure(api_key=GEMINI_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = """Сгенерируй простое предложение на английском с переводом на русский.
        Верни ТОЛЬКО JSON в формате:
        {"en": "предложение на английском", "ru": "перевод", "topic": "тема с эмодзи", "difficulty": "легко"}"""
        
        response = model.generate_content(prompt)
        generated = response.text
        print(f"📝 Gemini ответ: {generated[:100]}...")
        
        sentence = extract_json(generated)
        if sentence and all(field in sentence for field in ['en', 'ru', 'topic']):
            return sentence
    except Exception as e:
        print(f"⚠️ Gemini ошибка: {type(e).__name__}")
    
    return None

# ===== ОСНОВНЫЕ ФУНКЦИИ =====
def get_unique_ai_sentence():
    """Пробует всех провайдеров по очереди"""
    providers = [
        ("OpenRouter", generate_with_openrouter),
        ("Cerebras", generate_with_cerebras),
        ("Gemini", generate_with_gemini)
    ]
    
    for name, func in providers:
        print(f"\n🤖 Пробую {name}...")
        sentence = func()
        if sentence:
            if not is_used(sentence):
                print(f"✅ {name} сработал!")
                return sentence
            else:
                print(f"⚠️ {name} выдал уже использованное предложение")
    
    return None

def get_unique_db_sentence():
    """Берет неиспользованное предложение из базы"""
    sentences = load_sentences()
    if not sentences:
        return None
    
    used_ids = load_used_ids()
    available = [s for s in sentences if s['id'] not in used_ids]
    
    if not available:
        print("🔄 Все предложения использованы, начинаем заново")
        save_used_ids(set())
        available = sentences
    
    return random.choice(available)

def send_telegram_message(text):
    """Отправляет сообщение в Telegram"""
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ Нет BOT_TOKEN или CHAT_ID")
        return None
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        'chat_id': CHAT_ID,
        'text': text,
        'parse_mode': 'HTML'
    }
    
    try:
        response = requests.post(url, data=data, timeout=15)
        if response.status_code == 200:
            result = response.json()
            if result.get('ok'):
                print("✅ Сообщение отправлено в Telegram")
                return result
    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")
    
    return None

# ===== ГЛАВНАЯ ФУНКЦИЯ =====
def main():
    """Главная функция"""
    print("\n" + "="*60)
    print("🚀 ЗАПУСК БОТА (МУЛЬТИ-ПРОВАЙДЕР)")
    print("="*60)
    
    # Проверяем ключи
    print(f"\n📋 Наличие ключей:")
    print(f"   OpenRouter: {'✅' if OPENROUTER_KEY else '❌'}")
    print(f"   Cerebras: {'✅' if CEREBRAS_KEY else '❌'}")
    print(f"   Gemini: {'✅' if GEMINI_KEY else '❌'} (библиотека: {'✅' if GEMINI_AVAILABLE else '❌'})")
    
    current_hour = datetime.now().hour
    print(f"🕐 Текущее время UTC: {current_hour}:{datetime.now().minute}")
    
    # Ищем предложение
    print("\n🔍 ИЩЕМ УНИКАЛЬНОЕ ПРЕДЛОЖЕНИЕ...")
    
    sentence = get_unique_ai_sentence()
    
    if not sentence:
        print("\n📚 Пробую базу предложений...")
        sentence = get_unique_db_sentence()
    
    if not sentence:
        print("❌ НЕ УДАЛОСЬ ПОЛУЧИТЬ ПРЕДЛОЖЕНИЕ")
        return
    
    print(f"\n✅ ВЫБРАНО ПРЕДЛОЖЕНИЕ:")
    print(f"   🇬🇧 {sentence['en']}")
    print(f"   🇷🇺 {sentence['ru']}")
    print(f"   📚 {sentence['topic']}")
    
    # Формируем сообщение
    message = f"📝 <b>ЕЖЕДНЕВНЫЙ ДИКТАНТ</b>\n\n"
    message += f"<b>Тема:</b> {sentence['topic']}\n"
    message += f"<b>Сложность:</b> {sentence.get('difficulty', 'легко')}\n\n"
    message += f"🇬🇧 <b>Переведи на русский:</b>\n"
    message += f"<i>{sentence['en']}</i>\n\n"
    message += f"✍️ Пиши свой вариант в комментарии!"
    
    print("\n📨 ОТПРАВЛЯЕМ В TELEGRAM...")
    result = send_telegram_message(message)
    
    if result:
        mark_as_used(sentence)
        print("\n✅ ВСЕ ОПЕРАЦИИ ВЫПОЛНЕНЫ УСПЕШНО")
    else:
        print("\n❌ НЕ УДАЛОСЬ ОТПРАВИТЬ СООБЩЕНИЕ")
    
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
