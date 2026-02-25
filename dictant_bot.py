import json
import random
import os
import requests
import time
import hashlib
from datetime import datetime
import google.generativeai as genai  # для Gemini

# ===== НАСТРОЙКИ =====
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
SENTENCES_FILE = 'sentences.json'
USED_SENTENCES_FILE = 'used_sentences.txt'

# API ключи разных провайдеров
OPENROUTER_KEY = os.environ.get('OPENROUTER_KEY')
GEMINI_KEY = os.environ.get('GEMINI_KEY')
GROQ_KEY = os.environ.get('GROQ_KEY')
CEREBRAS_KEY = os.environ.get('CEREBRAS_KEY')
MISTRAL_KEY = os.environ.get('MISTRAL_KEY')

# URL-ы API
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
CEREBRAS_URL = "https://api.cerebras.ai/v1/chat/completions"
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"

# Конфигурация провайдеров (порядок = приоритет)
PROVIDERS = [
    {
        'name': 'OpenRouter',
        'enabled': bool(OPENROUTER_KEY),
        'type': 'openai',
        'url': OPENROUTER_URL,
        'key': OPENROUTER_KEY,
        'models': [
            "openrouter/free",
            "arcee-ai/trinity-large-preview:free",
            "z-ai/glm-4.5-air:free"
        ]
    },
    {
        'name': 'Google Gemini',
        'enabled': bool(GEMINI_KEY),
        'type': 'gemini',
        'key': GEMINI_KEY,
        'model': 'gemini-2.0-flash-exp'
    },
    {
        'name': 'Groq',
        'enabled': bool(GROQ_KEY),
        'type': 'openai',
        'url': GROQ_URL,
        'key': GROQ_KEY,
        'models': [
            "llama-3.3-70b-versatile",
            "mixtral-8x7b-32768",
            "gemma2-9b-it"
        ]
    },
    {
        'name': 'Cerebras',
        'enabled': bool(CEREBRAS_KEY),
        'type': 'openai',
        'url': CEREBRAS_URL,
        'key': CEREBRAS_KEY,
        'models': [
            "llama3.1-8b",
            "llama3.3-70b"
        ]
    },
    {
        'name': 'Mistral',
        'enabled': bool(MISTRAL_KEY),
        'type': 'mistral',
        'key': MISTRAL_KEY,
        'models': [
            "mistral-large-latest",
            "mistral-small-latest"
        ]
    }
]

def generate_with_gemini(provider):
    """Генерация через Google Gemini"""
    try:
        genai.configure(api_key=provider['key'])
        model = genai.GenerativeModel(provider['model'])
        
        prompt = """Сгенерируй простое предложение на английском с переводом на русский.
        Верни ТОЛЬКО JSON в таком формате (без пояснений, без ```):
        {
            "en": "предложение на английском (5-10 слов)",
            "ru": "перевод на русский",
            "topic": "тема с эмодзи",
            "difficulty": "легко"
        }
        """
        
        response = model.generate_content(prompt)
        generated = response.text
        
        # Очищаем ответ от markdown
        cleaned = generated.replace('```json', '').replace('```', '').strip()
        start = cleaned.find('{')
        end = cleaned.rfind('}') + 1
        
        if start != -1 and end > start:
            sentence = json.loads(cleaned[start:end])
            if all(field in sentence for field in ['en', 'ru', 'topic']):
                return sentence
    except Exception as e:
        print(f"⚠️ Gemini ошибка: {type(e).__name__}")
    return None

def generate_with_mistral(provider):
    """Генерация через Mistral AI"""
    try:
        model = random.choice(provider['models'])
        
        response = requests.post(
            provider['url'],
            headers={
                "Authorization": f"Bearer {provider['key']}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": [
                    {"role": "user", "content": """Сгенерируй простое предложение на английском с переводом на русский.
                    Верни ТОЛЬКО JSON:
                    {"en": "...", "ru": "...", "topic": "...", "difficulty": "легко"}"""}
                ],
                "temperature": 0.8,
                "max_tokens": 150
            },
            timeout=15
        )
        
        if response.status_code == 200:
            result = response.json()
            generated = result['choices'][0]['message']['content']
            
            cleaned = generated.replace('```json', '').replace('```', '').strip()
            start = cleaned.find('{')
            end = cleaned.rfind('}') + 1
            
            if start != -1 and end > start:
                sentence = json.loads(cleaned[start:end])
                if all(field in sentence for field in ['en', 'ru', 'topic']):
                    return sentence
    except Exception as e:
        print(f"⚠️ Mistral ошибка: {type(e).__name__}")
    return None

def generate_with_openai(provider):
    """Генерация через OpenAI-совместимые API (OpenRouter, Groq, Cerebras)"""
    try:
        model = random.choice(provider['models'])
        
        response = requests.post(
            provider['url'],
            headers={
                "Authorization": f"Bearer {provider['key']}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": [
                    {"role": "user", "content": """Сгенерируй простое предложение на английском с переводом на русский.
                    Верни ТОЛЬКО JSON:
                    {"en": "...", "ru": "...", "topic": "...", "difficulty": "легко"}"""}
                ],
                "temperature": 0.8,
                "max_tokens": 150
            },
            timeout=15
        )
        
        if response.status_code == 200:
            result = response.json()
            generated = result['choices'][0]['message']['content']
            
            cleaned = generated.replace('```json', '').replace('```', '').strip()
            start = cleaned.find('{')
            end = cleaned.rfind('}') + 1
            
            if start != -1 and end > start:
                sentence = json.loads(cleaned[start:end])
                if all(field in sentence for field in ['en', 'ru', 'topic']):
                    return sentence
    except Exception as e:
        print(f"⚠️ {provider['name']} ошибка: {type(e).__name__}")
    return None

def generate_with_ai():
    """Пробует всех провайдеров по очереди, пока не получит предложение"""
    
    for provider in PROVIDERS:
        if not provider['enabled']:
            continue
            
        print(f"\n🤖 Пробую {provider['name']}...")
        
        if provider['type'] == 'gemini':
            sentence = generate_with_gemini(provider)
        elif provider['type'] == 'mistral':
            sentence = generate_with_mistral(provider)
        else:  # openai-совместимые
            sentence = generate_with_openai(provider)
        
        if sentence:
            print(f"✅ {provider['name']} сработал!")
            return sentence
        
        time.sleep(1)  # Пауза между провайдерами
    
    print("❌ Ни один провайдер не сработал")
    return None

def load_sentences():
    """Загружает предложения из JSON"""
    try:
        with open(SENTENCES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data['sentences']
    except Exception as e:
        print(f"Ошибка загрузки sentences.json: {e}")
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
        print(f"Ошибка чтения использованных ID: {e}")
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

def get_unique_ai_sentence(max_attempts=2):
    """Пытается получить уникальное AI-предложение"""
    for attempt in range(max_attempts):
        print(f"🔄 Попытка {attempt + 1} из {max_attempts}")
        sentence = generate_with_ai()
        if sentence:
            if not is_used(sentence):
                print("✅ Найдено уникальное AI-предложение")
                return sentence
            else:
                print("⚠️ Предложение уже использовалось, пробуем другое...")
        time.sleep(1)
    return None

def get_unique_db_sentence():
    """Берет неиспользованное предложение из базы"""
    sentences = load_sentences()
    if not sentences:
        print("❌ База предложений пуста")
        return None
    
    used_ids = load_used_ids()
    print(f"📊 В базе: {len(sentences)} предложений, использовано: {len(used_ids)}")
    
    available = [s for s in sentences if s['id'] not in used_ids]
    
    if not available:
        print("🔄 Все предложения использованы, начинаем заново")
        save_used_ids(set())
        available = sentences
    
    sentence = random.choice(available)
    print(f"✅ Взято из базы (ID: {sentence['id']})")
    return sentence

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
        return None
    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")
        return None

def main():
    """Главная функция"""
    print("\n" + "="*50)
    print("🚀 ЗАПУСК БОТА (МУЛЬТИ-ПРОВАЙДЕР)")
    print("="*50)
    
    # Проверяем ключи
    print(f"🤖 BOT_TOKEN: {'✅' if BOT_TOKEN else '❌'}")
    print(f"📢 CHAT_ID: {'✅' if CHAT_ID else '❌'}")
    print("\n📋 Доступные провайдеры:")
    for p in PROVIDERS:
        status = "✅" if p['enabled'] else "❌"
        print(f"   {status} {p['name']}")
    
    current_hour = datetime.now().hour
    print(f"🕐 Текущее время UTC: {current_hour}:{datetime.now().minute}")
    
    # Для теста игнорируем время
    # if current_hour not in [6, 7]:
    #     print("⏰ Не время для отправки")
    #     return
    
    print("\n🔍 ИЩЕМ УНИКАЛЬНОЕ ПРЕДЛОЖЕНИЕ...")
    
    sentence = None
    
    # Пробуем AI (все провайдеры по очереди)
    if any(p['enabled'] for p in PROVIDERS):
        print("\n🤖 Пробую AI генерацию...")
        sentence = get_unique_ai_sentence()
    
    # Если AI не сработал, берем из базы
    if not sentence:
        print("\n📚 Использую базу предложений...")
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
    
    print("="*50 + "\n")

if __name__ == "__main__":
    main()
