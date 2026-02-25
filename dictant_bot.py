import json
import random
import os
import requests
import time
import hashlib
from datetime import datetime

# Импортируем Gemini (библиотека должна быть в requirements.txt)
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    print("⚠️ Gemini библиотека не установлена, Gemini будет отключен")
    GEMINI_AVAILABLE = False

# ===== НАСТРОЙКИ =====
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
SENTENCES_FILE = 'sentences.json'
USED_SENTENCES_FILE = 'used_sentences.txt'

# API ключи разных провайдеров
OPENROUTER_KEY = os.environ.get('OPENROUTER_KEY')
GEMINI_KEY = os.environ.get('GEMINI_KEY')
CEREBRAS_KEY = os.environ.get('CEREBRAS_KEY')

# URL-ы API
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
CEREBRAS_URL = "https://api.cerebras.ai/v1/chat/completions"

# Конфигурация провайдеров
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
        'enabled': bool(GEMINI_KEY) and GEMINI_AVAILABLE,
        'type': 'gemini',
        'key': GEMINI_KEY,
        'model': 'gemini-2.0-flash-exp'
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
    }
]

def test_provider(provider):
    """Тестирует конкретного провайдера и возвращает результат"""
    print(f"\n🔍 ТЕСТИРУЕМ {provider['name']}...")
    
    if not provider['enabled']:
        print(f"❌ {provider['name']} отключен (нет ключа или библиотеки)")
        return False
    
    prompt = """Сгенерируй простое предложение на английском с переводом на русский.
    Верни ТОЛЬКО JSON:
    {"en": "предложение", "ru": "перевод", "topic": "тема с эмодзи", "difficulty": "легко"}
    Пример: {"en": "I like coffee", "ru": "Я люблю кофе", "topic": "☕ Еда", "difficulty": "легко"}"""
    
    try:
        if provider['type'] == 'gemini':
            genai.configure(api_key=provider['key'])
            model = genai.GenerativeModel(provider['model'])
            response = model.generate_content(prompt)
            generated = response.text
            print(f"📝 Ответ: {generated[:100]}...")
            
            cleaned = generated.replace('```json', '').replace('```', '').strip()
            start = cleaned.find('{')
            end = cleaned.rfind('}') + 1
            
            if start != -1 and end > start:
                sentence = json.loads(cleaned[start:end])
                if all(field in sentence for field in ['en', 'ru', 'topic']):
                    print(f"✅ {provider['name']} РАБОТАЕТ!")
                    print(f"   Пример: {sentence['en']}")
                    return True
                    
        else:  # openai-совместимые
            model = random.choice(provider['models'])
            response = requests.post(
                provider['url'],
                headers={
                    "Authorization": f"Bearer {provider['key']}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.8,
                    "max_tokens": 150
                },
                timeout=15
            )
            
            print(f"📊 Статус: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                generated = result['choices'][0]['message']['content']
                print(f"📝 Ответ: {generated[:100]}...")
                
                cleaned = generated.replace('```json', '').replace('```', '').strip()
                start = cleaned.find('{')
                end = cleaned.rfind('}') + 1
                
                if start != -1 and end > start:
                    sentence = json.loads(cleaned[start:end])
                    if all(field in sentence for field in ['en', 'ru', 'topic']):
                        print(f"✅ {provider['name']} РАБОТАЕТ!")
                        print(f"   Пример: {sentence['en']}")
                        return True
    except Exception as e:
        print(f"❌ Ошибка: {type(e).__name__}")
    
    print(f"❌ {provider['name']} НЕ РАБОТАЕТ")
    return False

def main():
    """Главная функция - тестирование всех провайдеров"""
    print("\n" + "="*60)
    print("🚀 ТЕСТИРОВАНИЕ ВСЕХ AI ПРОВАЙДЕРОВ")
    print("="*60)
    
    # Проверяем ключи
    print(f"\n📋 Наличие ключей:")
    print(f"   OpenRouter: {'✅' if OPENROUTER_KEY else '❌'}")
    print(f"   Gemini: {'✅' if GEMINI_KEY else '❌'} (библиотека: {'✅' if GEMINI_AVAILABLE else '❌'})")
    print(f"   Cerebras: {'✅' if CEREBRAS_KEY else '❌'}")
    
    # Тестируем каждого провайдера
    results = []
    for provider in PROVIDERS:
        result = test_provider(provider)
        results.append((provider['name'], result))
        time.sleep(2)  # Пауза между тестами
    
    # Выводим итоги
    print("\n" + "="*60)
    print("📊 ИТОГИ ТЕСТИРОВАНИЯ")
    print("="*60)
    
    working = [name for name, status in results if status]
    not_working = [name for name, status in results if not status and any(p['enabled'] for p in PROVIDERS if p['name'] == name)]
    
    if working:
        print(f"\n✅ РАБОТАЮТ: {', '.join(working)}")
    if not_working:
        print(f"\n❌ НЕ РАБОТАЮТ: {', '.join(not_working)}")
    
    print("\n" + "="*60)
    
    # Если есть работающие, пробуем отправить тестовое сообщение
    if working and BOT_TOKEN and CHAT_ID:
        print("\n📨 Отправляю тестовое сообщение в Telegram...")
        
        # Берем первый работающий провайдер
        for provider in PROVIDERS:
            if provider['name'] in working:
                print(f"🤖 Использую {provider['name']}...")
                # Здесь можно добавить код отправки
                break
    
    print("\n🏁 Тестирование завершено")

if __name__ == "__main__":
    main()
