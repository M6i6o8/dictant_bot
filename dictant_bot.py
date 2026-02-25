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
OPENROUTER_KEY = os.environ.get('OPENROUTER_KEY')  # Ключ от OpenRouter
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
        return []

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
        print(f"❌ Ошибка сохранения использованных ID: {e}")

def mark_as_used(sentence):
    """Помечает предложение как использованное"""
    used_ids = load_used_ids()
    
    if 'id' not in sentence:
        # Создаем уникальный ID на основе текста
        text_hash = hashlib.md5(sentence['en'].encode()).hexdigest()[:8]
        sentence['id'] = int(text_hash, 16) % 1000000
    
    used_ids.add(sentence['id'])
    save_used_ids(used_ids)
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
    """Генерирует новое предложение через OpenRouter (бесплатные модели)"""
    
    if not OPENROUTER_KEY:
        print("❌ Нет API ключа OpenRouter")
        return None
    
    # Список бесплатных моделей OpenRouter
    models = [
        "deepseek/deepseek-r1:free",
        "deepseek/deepseek-chat:free",
        "google/gemini-2.0-flash-exp:free",
        "meta-llama/llama-3.2-3b-instruct:free",
        "microsoft/phi-3.5-mini-128k-instruct:free"
    ]
    
    model = random.choice(models)  # Выбираем случайную модель
    print(f"🤖 Использую модель: {model}")
    
    prompt = """Ты - помощник для изучения английского языка. 
    Сгенерируй УНИКАЛЬНОЕ предложение на английском с переводом на русский.
    
    Важно: 
    - Предложение должно быть простым и полезным для повседневной жизни
    - Никогда не повторяйся
    - Используй разные темы (путешествия, еда, работа, семья, хобби, технологии, погода, здоровье)
    
    Верни ТОЛЬКО JSON (без пояснений, без ```, без лишнего текста):
    {
        "en": "предложение на английском",
        "ru": "перевод на русский", 
        "topic": "тема с эмодзи",
        "difficulty": "легко/средне/сложно"
    }
    
    Примеры хороших ответов:
    {"en": "I love reading books in the evening", "ru": "Я люблю читать книги вечером", "topic": "📚 Хобби", "difficulty": "легко"}
    {"en": "She is learning to play the guitar", "ru": "Она учится играть на гитаре", "topic": "🎸 Музыка", "difficulty": "средне"}
    {"en": "The weather is getting colder every day", "ru": "Погода становится холоднее с каждым днем", "topic": "☀️ Погода", "difficulty": "легко"}
    """
    
    try:
        response = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/",  # Можно указать свой сайт
                "X-Title": "English Dictant Bot"  # Название проекта
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.9,
                "max_tokens": 200
            },
            timeout=20
        )
        
        if response.status_code == 200:
            result = response.json()
            generated = result['choices'][0]['message']['content']
            print(f"📝 Сырой ответ: {generated[:150]}...")
            
            # Ищем JSON в ответе
            start = generated.find('{')
            end = generated.rfind('}') + 1
            
            if start != -1 and end > start:
                json_str = generated[start:end]
                try:
                    sentence = json.loads(json_str)
                    
                    # Проверяем обязательные поля
                    required_fields = ['en', 'ru', 'topic']
                    if all(field in sentence for field in required_fields):
                        # Добавляем difficulty если нет
                        if 'difficulty' not in sentence:
                            sentence['difficulty'] = 'легко'
                        
                        # Проверяем уникальность
                        if not is_used(sentence):
                            print(f"✅ Уникальное предложение получено: {sentence['en'][:50]}...")
                            return sentence
                        else:
                            print("⚠️ Такое предложение уже было")
                    else:
                        print(f"❌ Нет обязательных полей. Есть: {list(sentence.keys())}")
                except json.JSONDecodeError as e:
                    print(f"❌ Ошибка парсинга JSON: {e}")
            else:
                print("❌ JSON не найден в ответе")
        else:
            print(f"❌ Ошибка OpenRouter API: {response.status_code}")
            print(f"Ответ: {response.text[:200]}")
        
        return None
        
    except requests.exceptions.Timeout:
        print("⏰ Таймаут OpenRouter API")
        return None
    except Exception as e:
        print(f"❌ Ошибка генерации: {e}")
        return None

def get_unique_ai_sentence(max_attempts=3):
    """Пытается получить уникальное AI-предложение"""
    for attempt in range(max_attempts):
        print(f"🔄 Попытка {attempt + 1} из {max_attempts}")
        sentence = generate_with_openrouter()
        if sentence and not is_used(sentence):
            return sentence
        if sentence:
            print("⚠️ Получили повтор, пробуем снова...")
        time.sleep(1)  # Пауза между попытками
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
    print(f"📚 Доступно из базы: {len(available)}")
    
    # Если все использованы - очищаем историю
    if not available:
        print("🔄 Все предложения из базы использованы, начинаем заново")
        save_used_ids(set())
        available = sentences
    
    return random.choice(available) if available else None

def send_telegram_message(text):
    """Отправляет сообщение в Telegram"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        'chat_id': CHAT_ID,
        'text': text,
        'parse_mode': 'HTML'
    }
    
    try:
        print(f"📤 Отправляем в чат {CHAT_ID}")
        response = requests.post(url, data=data, timeout=10)
        result = response.json()
        
        if result.get('ok'):
            print("✅ Сообщение отправлено успешно")
        else:
            print(f"❌ Ошибка Telegram: {result}")
        return result
    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")
        return None

def main():
    """Главная функция"""
    print("🚀 Запуск бота...")
    print(f"🕐 Время UTC: {datetime.now().hour}:{datetime.now().minute}")
    
    # Проверяем наличие ключа
    if OPENROUTER_KEY:
        print("✅ OpenRouter ключ найден")
    else:
        print("⚠️ OpenRouter ключ не найден, буду использовать только базу")
    
    current_hour = datetime.now().hour
    
    # Работаем только в нужные часы (6 и 7 UTC = 9 и 10 МСК)
    if current_hour not in [6, 7]:
        print("⏰ Не время для отправки. Ждем 6 или 7 UTC")
        return
    
    print("🔍 Ищем уникальное предложение...")
    sentence = None
    
    # Сначала пробуем AI (если есть ключ)
    if OPENROUTER_KEY:
        print("🤖 Пробую AI генерацию через OpenRouter...")
        sentence = get_unique_ai_sentence()
    
    # Если AI не сработал, берем из базы
    if not sentence:
        print("📚 Использую базу предложений...")
        sentence = get_unique_db_sentence()
    
    if not sentence:
        print("❌ Не удалось получить предложение")
        return
    
    print(f"✅ Выбрано: {sentence.get('en', '')[:100]}...")
    
    # Формируем и отправляем сообщение
    if current_hour == 6:  # 9:00 МСК - задание
        message = f"📝 <b>Ежедневный диктант</b>\n\n"
        message += f"<b>Тема:</b> {sentence['topic']}\n"
        message += f"<b>Сложность:</b> {sentence.get('difficulty', 'легко')}\n\n"
        message += f"🇬🇧 <b>Переведи на русский:</b>\n"
        message += f"<i>{sentence['en']}</i>\n\n"
        message += f"⏳ <b>Ответ придет в 10:00</b>\n"
        message += f"✍️ Пиши свой вариант в комментарии!"
        
        result = send_telegram_message(message)
        if result and result.get('ok'):
            mark_as_used(sentence)
            print("✅ Предложение помечено как использованное")
            
    elif current_hour == 7:  # 10:00 МСК - проверка
        message = f"📝 <b>Проверка диктанта</b>\n\n"
        message += f"🇬🇧 <b>Было:</b> {sentence['en']}\n"
        message += f"🇷🇺 <b>Правильный перевод:</b>\n"
        message += f"<i>{sentence['ru']}</i>\n\n"
        message += f"📊 <b>Разбор:</b>\n"
        message += f"• Тема: {sentence['topic']}\n"
        message += f"• Сложность: {sentence.get('difficulty', 'легко')}\n\n"
        message += f"💪 Как твой вариант? Напиши в комментариях!"
        
        send_telegram_message(message)
    
    print("🏁 Завершено")

if __name__ == "__main__":
    main()
