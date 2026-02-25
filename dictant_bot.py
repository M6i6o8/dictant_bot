import json
import random
import os
import requests
import time
from datetime import datetime
import hashlib

# ===== НАСТРОЙКИ =====
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
OPENROUTER_KEY = os.environ.get('OPENROUTER_KEY')
SENTENCES_FILE = 'sentences.json'
USED_SENTENCES_FILE = 'used_sentences.txt'

# OpenRouter API
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

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

def test_all_models():
    """Тестирует все бесплатные модели и возвращает список работающих"""
    
    print("\n" + "="*60)
    print("🔬 НАЧИНАЕМ ТЕСТИРОВАНИЕ ВСЕХ БЕСПЛАТНЫХ МОДЕЛЕЙ")
    print("="*60)
    
    # Все потенциально бесплатные модели OpenRouter
    test_models = [
        # Топ модели
        "openrouter/free",  # Автоматический роутер
        "arcee-ai/trinity-large-preview:free",
        "stepfun/step-3.5-flash:free",
        "z-ai/glm-4.5-air:free",
        "deepseek/deepseek-r1:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "google/gemma-3-27b-it:free",
        "z-ai/glm-5-pony-alpha:free",
        "nvidia/nemotron-3-nano:free",
        "nvidia/nemotron-nano-2-vl:free",
        "qwen/qwen3-235b-thinking:free",
        
        # Дополнительные бесплатные
        "google/gemini-2.0-flash-exp:free",
        "deepseek/deepseek-chat:free",
        "meta-llama/llama-3.2-3b-instruct:free",
        "qwen/qwen-2.5-7b-instruct:free",
        "microsoft/phi-3.5-mini-128k-instruct:free",
        "mistralai/mistral-7b-instruct:free",
        "cognitivecomputations/dolphin-2.9-llama3-8b:free",
        "microsoft/phi-3-mini-128k-instruct:free",
        "google/gemma-2-9b-it:free",
        "cohere/command-r-plus-08-2024:free",
        "cohere/command-r-03-2024:free"
    ]
    
    working_models = []
    
    for i, model in enumerate(test_models, 1):
        print(f"\n🔍 Тест {i}/{len(test_models)}: {model}")
        print("-" * 40)
        
        prompt = """Ты - помощник для изучения английского языка. 
        Сгенерируй простое предложение на английском с переводом на русский.
        
        Верни ТОЛЬКО JSON:
        {
            "en": "предложение на английском",
            "ru": "перевод на русский",
            "topic": "тема с эмодзи",
            "difficulty": "легко"
        }
        
        Пример: {"en": "I like coffee", "ru": "Я люблю кофе", "topic": "☕ Еда", "difficulty": "легко"}
        """
        
        try:
            response = requests.post(
                OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {OPENROUTER_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/dictant_bot",
                    "X-Title": "English Dictant Bot"
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": 150
                },
                timeout=15
            )
            
            print(f"📊 Статус: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                # Какая модель реально ответила (для роутера)
                actual_model = result.get('model', model)
                
                generated = result['choices'][0]['message']['content']
                print(f"📝 Ответ: {generated[:100]}...")
                
                # Пытаемся найти JSON
                cleaned = generated.replace('```json', '').replace('```', '').strip()
                start = cleaned.find('{')
                end = cleaned.rfind('}') + 1
                
                if start != -1 and end > start:
                    try:
                        sentence = json.loads(cleaned[start:end])
                        if all(field in sentence for field in ['en', 'ru', 'topic']):
                            print(f"✅✅✅ РАБОТАЕТ! Реальная модель: {actual_model}")
                            working_models.append({
                                'запрошенная': model,
                                'реальная': actual_model,
                                'пример': sentence['en'][:50]
                            })
                        else:
                            print("❌ Ответ не содержит нужных полей")
                    except json.JSONDecodeError:
                        print("❌ Невалидный JSON")
                else:
                    print("❌ JSON не найден")
            else:
                print(f"❌ Ошибка {response.status_code}: {response.text[:100]}")
                
        except Exception as e:
            print(f"❌ Исключение: {type(e).__name__}")
        
        time.sleep(1)  # Пауза между запросами
    
    # Выводим итоги
    print("\n" + "="*60)
    print("📊 ИТОГИ ТЕСТИРОВАНИЯ")
    print("="*60)
    
    if working_models:
        print(f"\n✅ НАЙДЕНО РАБОТАЮЩИХ МОДЕЛЕЙ: {len(working_models)}")
        print("\n📋 СПИСОК РАБОТАЮЩИХ МОДЕЛЕЙ:")
        for wm in working_models:
            print(f"   • {wm['запрошенная']}")
            print(f"     → Реальная: {wm['реальная']}")
            print(f"     → Пример: {wm['пример']}...\n")
    else:
        print("\n❌ НЕ НАЙДЕНО НИ ОДНОЙ РАБОТАЮЩЕЙ МОДЕЛИ")
    
    print("="*60)
    return working_models

def generate_with_openrouter():
    """Генерирует предложение используя рабочую модель"""
    
    if not OPENROUTER_KEY:
        print("❌ Нет API ключа OpenRouter")
        return None
    
    # Используем проверенные рабочие модели (обновить после теста)
    working_models = [
        "openrouter/free",  # Если работает
        "deepseek/deepseek-r1:free",
        "google/gemini-2.0-flash-exp:free",
        "meta-llama/llama-3.3-70b-instruct:free"
    ]
    
    model = random.choice(working_models)
    print(f"🤖 Использую модель: {model}")
    
    prompt = """Ты - помощник для изучения английского языка. 
    Сгенерируй простое предложение на английском с переводом на русский.
    
    Верни ТОЛЬКО JSON:
    {
        "en": "предложение на английском",
        "ru": "перевод на русский",
        "topic": "тема с эмодзи",
        "difficulty": "легко"
    }
    """
    
    try:
        response = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/dictant_bot",
                "X-Title": "English Dictant Bot"
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.8,
                "max_tokens": 200
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            actual_model = result.get('model', model)
            print(f"🤖 Реальная модель: {actual_model}")
            
            generated = result['choices'][0]['message']['content']
            cleaned = generated.replace('```json', '').replace('```', '').strip()
            
            start = cleaned.find('{')
            end = cleaned.rfind('}') + 1
            
            if start != -1 and end > start:
                sentence = json.loads(cleaned[start:end])
                if all(field in sentence for field in ['en', 'ru', 'topic']):
                    if 'difficulty' not in sentence:
                        sentence['difficulty'] = 'легко'
                    return sentence
        return None
    except:
        return None

def main():
    """Главная функция"""
    print("\n" + "="*50)
    print("🚀 ЗАПУСК БОТА-ДЕТЕКТИВА")
    print("="*50)
    
    # Проверяем ключи
    print(f"🤖 BOT_TOKEN: {'✅' if BOT_TOKEN else '❌'}")
    print(f"📢 CHAT_ID: {'✅' if CHAT_ID else '❌'}")
    print(f"🔑 OPENROUTER_KEY: {'✅' if OPENROUTER_KEY else '❌'}")
    
    # Запускаем тестирование моделей
    working_models = test_all_models()
    
    # Если нужно отправить тестовое сообщение с рабочей моделью
    if working_models and CHAT_ID and BOT_TOKEN:
        print("\n📨 Отправляю тестовое сообщение с рабочей моделью...")
        sentence = generate_with_openrouter()
        if sentence:
            message = f"📝 <b>ТЕСТ С РАБОЧЕЙ МОДЕЛЬЮ</b>\n\n"
            message += f"<b>Тема:</b> {sentence['topic']}\n"
            message += f"🇬🇧 {sentence['en']}\n"
            message += f"🇷🇺 {sentence['ru']}"
            
            # Отправка в Telegram (код отправки опущен для краткости)
            print(f"✅ Сгенерировано: {sentence['en']}")
    
    print("\n" + "="*50)

if __name__ == "__main__":
    main()
