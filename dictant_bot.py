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
        # Возвращаем тестовые данные если файл не найден
        return [
            {"id": 1, "en": "I like to read books", "ru": "Я люблю читать книги", "topic": "📚 Хобби", "difficulty": "легко"},
            {"id": 2, "en": "She works as a doctor", "ru": "Она работает врачом", "topic": "💼 Работа", "difficulty": "легко"},
            {"id": 3, "en": "They are playing football", "ru": "Они играют в футбол", "topic": "⚽ Спорт", "difficulty": "легко"}
        ]

def load_used_ids():
    """Загружает список использованных ID предложений"""
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
        # Создаем уникальный ID на основе текста
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

def generate_with_openrouter():
    """Генерирует новое предложение через OpenRouter"""
    
    if not OPENROUTER_KEY:
        print("❌ Нет API ключа OpenRouter")
        return None
    
    # Рабочие бесплатные модели OpenRouter
    models = [
        "deepseek/deepseek-chat:free",
        "google/gemini-2.0-flash-exp:free",
        "meta-llama/llama-3.2-3b-instruct:free",
        "qwen/qwen-2.5-7b-instruct:free",
        "microsoft/phi-3.5-mini-128k-instruct:free"
    ]
    
    model = random.choice(models)
    print(f"🤖 Использую модель: {model}")
    
    prompt = """Ты - помощник для изучения английского языка. 
    Сгенерируй простое предложение на английском с переводом на русский.
    
    Требования:
    - Предложение должно быть из 5-10 слов
    - Тема: повседневная жизнь (семья, работа, еда, путешествия, хобби)
    - Уровень: beginner/intermediate
    
    Верни ТОЛЬКО JSON в таком формате:
    {
        "en": "предложение на английском",
        "ru": "перевод на русский",
        "topic": "тема с эмодзи",
        "difficulty": "легко"
    }
    
    Пример ответа:
    {"en": "I usually drink coffee in the morning", "ru": "Я обычно пью кофе утром", "topic": "☕ Еда", "difficulty": "легко"}
    """
    
    try:
        print("📡 Отправляю запрос к OpenRouter...")
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
        
        print(f"📊 Статус ответа: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            generated = result['choices'][0]['message']['content']
            print(f"📝 Сырой ответ: {generated[:150]}...")
            
            # Очищаем ответ от markdown
            cleaned = generated.replace('```json', '').replace('```', '').strip()
            
            # Ищем JSON
            start = cleaned.find('{')
            end = cleaned.rfind('}') + 1
            
            if start != -1 and end > start:
                try:
                    json_str = cleaned[start:end]
                    sentence = json.loads(json_str)
                    
                    # Проверяем обязательные поля
                    required = ['en', 'ru', 'topic']
                    if all(field in sentence for field in required):
                        if 'difficulty' not in sentence:
                            sentence['difficulty'] = 'легко'
                        
                        print(f"✅ Успешно сгенерировано: {sentence['en'][:50]}...")
                        return sentence
                    else:
                        print(f"❌ Нет обязательных полей. Есть: {list(sentence.keys())}")
                except json.JSONDecodeError as e:
                    print(f"❌ Ошибка парсинга JSON: {e}")
            else:
                print("❌ JSON не найден в ответе")
        else:
            print(f"❌ Ошибка API: {response.status_code}")
            print(f"Ответ: {response.text[:200]}")
            
    except requests.exceptions.Timeout:
        print("⏰ Таймаут при запросе к OpenRouter")
    except requests.exceptions.ConnectionError:
        print("🔌 Ошибка соединения с OpenRouter")
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
    
    return None

def get_unique_ai_sentence(max_attempts=3):
    """Пытается получить уникальное AI-предложение"""
    for attempt in range(max_attempts):
        print(f"🔄 Попытка {attempt + 1} из {max_attempts}")
        sentence = generate_with_openrouter()
        if sentence:
            if not is_used(sentence):
                print("✅ Найдено уникальное AI-предложение")
                return sentence
            else:
                print("⚠️ Предложение уже использовалось, пробуем другое...")
        else:
            print("⚠️ Не удалось сгенерировать, пробуем снова...")
        time.sleep(2)
    return None

def get_unique_db_sentence():
    """Берет неиспользованное предложение из базы"""
    sentences = load_sentences()
    if not sentences:
        print("❌ База предложений пуста")
        return None
    
    used_ids = load_used_ids()
    print(f"📊 В базе: {len(sentences)} предложений, использовано: {len(used_ids)}")
    
    # Ищем неиспользованные
    available = [s for s in sentences if s['id'] not in used_ids]
    
    if not available:
        print("🔄 Все предложения использованы, начинаем заново")
        save_used_ids(set())
        available = sentences
    
    sentence = random.choice(available)
    print(f"✅ Взято из базы (ID: {sentence['id']})")
    return sentence

def send_telegram_message(text):
    """Отправляет сообщение в Telegram с подробным логированием"""
    
    if not BOT_TOKEN:
        print("❌ Нет BOT_TOKEN")
        return None
    
    if not CHAT_ID:
        print("❌ Нет CHAT_ID")
        return None
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        'chat_id': CHAT_ID,
        'text': text,
        'parse_mode': 'HTML'
    }
    
    print(f"\n📤 ===== НАЧАЛО ОТПРАВКИ В TELEGRAM =====")
    print(f"📤 Чат ID: {CHAT_ID}")
    print(f"📤 Длина сообщения: {len(text)} символов")
    print(f"📤 Первые 100 символов: {text[:100]}...")
    
    try:
        print("📡 Отправка запроса...")
        response = requests.post(url, data=data, timeout=15)
        print(f"📊 HTTP статус: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"📦 Ответ API: {result}")
            
            if result.get('ok'):
                print("✅✅✅ СООБЩЕНИЕ УСПЕШНО ОТПРАВЛЕНО! ✅✅✅")
                print(f"📨 ID сообщения: {result['result']['message_id']}")
                return result
            else:
                print(f"❌ Ошибка Telegram API: {result}")
                print(f"❌ Описание: {result.get('description', 'Нет описания')}")
        else:
            print(f"❌ HTTP ошибка: {response.status_code}")
            print(f"❌ Текст ответа: {response.text[:200]}")
            
    except requests.exceptions.Timeout:
        print("❌ Таймаут при отправке")
    except requests.exceptions.ConnectionError:
        print("❌ Ошибка соединения")
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        print(f"❌ Тип ошибки: {type(e)}")
    
    print("📤 ===== КОНЕЦ ОТПРАВКИ =====\n")
    return None

def main():
    """Главная функция"""
    print("\n" + "="*50)
    print("🚀 ЗАПУСК БОТА")
    print("="*50)
    
    # Проверяем наличие всех ключей
    print(f"🤖 BOT_TOKEN: {'✅' if BOT_TOKEN else '❌'} (первые символы: {BOT_TOKEN[:10] if BOT_TOKEN else 'нет'})")
    print(f"📢 CHAT_ID: {'✅' if CHAT_ID else '❌'} ({CHAT_ID if CHAT_ID else 'нет'})")
    print(f"🔑 OPENROUTER_KEY: {'✅' if OPENROUTER_KEY else '❌'}")
    
    current_hour = datetime.now().hour
    print(f"🕐 Текущее время UTC: {current_hour}:{datetime.now().minute}")
    
    # ВРЕМЕННО отключаем проверку времени для теста
    # if current_hour not in [6, 7]:
    #     print("⏰ Не время для отправки")
    #     print("="*50)
    #     return
    
    print("\n🔍 ИЩЕМ УНИКАЛЬНОЕ ПРЕДЛОЖЕНИЕ...")
    
    sentence = None
    
    # Пробуем AI
    if OPENROUTER_KEY:
        print("\n🤖 Пробую AI генерацию через OpenRouter...")
        sentence = get_unique_ai_sentence()
    
    # Если AI не сработал, берем из базы
    if not sentence:
        print("\n📚 Использую базу предложений...")
        sentence = get_unique_db_sentence()
    
    if not sentence:
        print("❌ НЕ УДАЛОСЬ ПОЛУЧИТЬ ПРЕДЛОЖЕНИЕ")
        print("="*50)
        return
    
    print(f"\n✅ ВЫБРАНО ПРЕДЛОЖЕНИЕ:")
    print(f"   🇬🇧 EN: {sentence['en']}")
    print(f"   🇷🇺 RU: {sentence['ru']}")
    print(f"   📚 Тема: {sentence['topic']}")
    
    # Формируем сообщение для отправки
    message = f"📝 <b>ТЕСТОВЫЙ ДИКТАНТ</b>\n\n"
    message += f"<b>Тема:</b> {sentence['topic']}\n"
    message += f"<b>Сложность:</b> {sentence.get('difficulty', 'легко')}\n\n"
    message += f"🇬🇧 <b>Переведи на русский:</b>\n"
    message += f"<i>{sentence['en']}</i>\n\n"
    message += f"⏳ <b>Проверка будет позже</b>\n"
    message += f"✍️ Пиши свой вариант в комментарии!"
    
    print("\n📨 ОТПРАВЛЯЕМ В TELEGRAM...")
    result = send_telegram_message(message)
    
    if result and result.get('ok'):
        mark_as_used(sentence)
        print("\n✅ ВСЕ ОПЕРАЦИИ ВЫПОЛНЕНЫ УСПЕШНО")
    else:
        print("\n❌ НЕ УДАЛОСЬ ОТПРАВИТЬ СООБЩЕНИЕ")
    
    print("="*50 + "\n")

if __name__ == "__main__":
    main()
