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
LAST_SENTENCE_FILE = 'last_sentence.json'

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
    """Загружает предложения из JSON"""
    try:
        with open(SENTENCES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data['sentences']
    except Exception as e:
        print(f"⚠️ Ошибка загрузки sentences.json: {e}")
        return [
            {"id": 1, "en": "I like to read books", "ru": "Я люблю читать книги", "topic": "📚 Хобби", "difficulty": "легко", "explanation": "Present Simple для выражения привычки. После I глагол без окончаний."},
            {"id": 2, "en": "She works as a doctor", "ru": "Она работает врачом", "topic": "💼 Работа", "difficulty": "легко", "explanation": "Present Simple. После she/he/it добавляем -s к глаголу."},
            {"id": 3, "en": "They are playing football now", "ru": "Они сейчас играют в футбол", "topic": "⚽ Спорт", "difficulty": "средне", "explanation": "Present Continuous (are + playing) для действия прямо сейчас."}
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

# ===== ФУНКЦИИ СОХРАНЕНИЯ ПОСЛЕДНЕГО ПРЕДЛОЖЕНИЯ =====
def save_last_sentence(sentence):
    """Сохраняет последнее предложение для ответа"""
    try:
        # Создаем копию без лишних полей
        save_data = {
            'en': sentence['en'],
            'ru': sentence['ru'],
            'topic': sentence.get('topic', 'Тема'),
            'difficulty': sentence.get('difficulty', 'легко'),
            'explanation': sentence.get('explanation', 'Разбор будет позже')
        }
        
        # Пробуем сохранить в текущую директорию
        with open(LAST_SENTENCE_FILE, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Предложение сохранено в {LAST_SENTENCE_FILE}")
        
        # Проверяем что файл реально создался
        if os.path.exists(LAST_SENTENCE_FILE):
            file_size = os.path.getsize(LAST_SENTENCE_FILE)
            print(f"📁 Размер файла: {file_size} байт")
            return True
        else:
            print(f"❌ Файл {LAST_SENTENCE_FILE} не создался")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка сохранения предложения: {e}")
        return False

def load_last_sentence():
    """Загружает последнее предложение для ответа"""
    try:
        if not os.path.exists(LAST_SENTENCE_FILE):
            print(f"⚠️ Файл {LAST_SENTENCE_FILE} не найден")
            return None
        
        file_size = os.path.getsize(LAST_SENTENCE_FILE)
        print(f"📁 Размер файла: {file_size} байт")
        
        if file_size == 0:
            print("⚠️ Файл пустой")
            return None
        
        with open(LAST_SENTENCE_FILE, 'r', encoding='utf-8') as f:
            sentence = json.load(f)
        
        print(f"✅ Предложение загружено: {sentence.get('en', '')[:50]}...")
        return sentence
        
    except json.JSONDecodeError as e:
        print(f"❌ Ошибка парсинга JSON: {e}")
        return None
    except Exception as e:
        print(f"❌ Ошибка загрузки: {e}")
        return None

# ===== ФУНКЦИИ ГЕНЕРАЦИИ =====
def generate_with_gemini():
    """Генерация через Google Gemini (приоритет 1)"""
    if not GEMINI_AVAILABLE or not GEMINI_KEY:
        return None
    
    try:
        genai.configure(api_key=GEMINI_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = """Ты - профессиональный преподаватель английского языка. Создай учебное предложение с подробным грамматическим разбором.
        
        Требования:
        - Предложение должно быть полезным для повседневной жизни
        - Уровень: от легкого до среднего
        - Разбор должен быть понятным и подробным
        
        Верни ТОЛЬКО JSON:
        {
            "en": "предложение на английском (5-10 слов)",
            "ru": "перевод на русский",
            "topic": "тема с эмодзи",
            "difficulty": "легко/средне",
            "explanation": "подробное объяснение грамматики на русском (3-4 предложения)"
        }"""
        
        response = model.generate_content(prompt)
        generated = response.text
        print(f"📝 Gemini ответ: {generated[:150]}...")
        
        sentence = extract_json(generated)
        if sentence and all(field in sentence for field in ['en', 'ru', 'topic', 'explanation']):
            return sentence
    except Exception as e:
        print(f"⚠️ Gemini ошибка: {type(e).__name__}")
    
    return None

def generate_with_cerebras():
    """Генерация через Cerebras (приоритет 2)"""
    if not CEREBRAS_KEY:
        return None
    
    models = ["llama3.1-8b", "llama3.3-70b"]
    model = random.choice(models)
    
    prompt = """Ты - опытный преподаватель английского. Сгенерируй предложение с грамматическим разбором.
    
    Верни ТОЛЬКО JSON:
    {
        "en": "предложение на английском",
        "ru": "перевод на русский",
        "topic": "тема с эмодзи",
        "difficulty": "легко/средне",
        "explanation": "подробное объяснение грамматики на русском"
    }"""
    
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
                "max_tokens": 400
            },
            timeout=25
        )
        
        if response.status_code == 200:
            result = response.json()
            generated = result['choices'][0]['message']['content']
            print(f"📝 Cerebras ответ: {generated[:150]}...")
            
            sentence = extract_json(generated)
            if sentence and all(field in sentence for field in ['en', 'ru', 'topic', 'explanation']):
                return sentence
    except Exception as e:
        print(f"⚠️ Cerebras ошибка: {type(e).__name__}")
    
    return None

def generate_with_openrouter():
    """Генерация через OpenRouter (последний приоритет)"""
    if not OPENROUTER_KEY:
        return None
    
    models = [
        "openrouter/free",
        "arcee-ai/trinity-large-preview:free",
        "z-ai/glm-4.5-air:free"
    ]
    
    model = random.choice(models)
    
    prompt = """Сгенерируй учебное предложение на английском с переводом и разбором.
    
    Верни JSON:
    {
        "en": "предложение на английском",
        "ru": "перевод на русский",
        "topic": "тема с эмодзи",
        "difficulty": "легко/средне",
        "explanation": "объяснение грамматики"
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
                "max_tokens": 400
            },
            timeout=25
        )
        
        if response.status_code == 200:
            result = response.json()
            generated = result['choices'][0]['message']['content']
            print(f"📝 OpenRouter ответ: {generated[:150]}...")
            
            sentence = extract_json(generated)
            if sentence and all(field in sentence for field in ['en', 'ru', 'topic', 'explanation']):
                return sentence
    except Exception as e:
        print(f"⚠️ OpenRouter ошибка: {type(e).__name__}")
    
    return None

# ===== ОСНОВНЫЕ ФУНКЦИИ =====
def get_unique_ai_sentence():
    """Пробует всех провайдеров в правильном порядке"""
    providers = [
        ("Gemini", generate_with_gemini),
        ("Cerebras", generate_with_cerebras),
        ("OpenRouter", generate_with_openrouter)
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
        print(f"📤 Отправка в Telegram...")
        response = requests.post(url, data=data, timeout=15)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('ok'):
                print("✅ Сообщение отправлено")
                return result
            else:
                print(f"❌ Ошибка Telegram API: {result}")
        else:
            print(f"❌ HTTP ошибка: {response.status_code}")
    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")
    
    return None

# ===== ГЛАВНАЯ ФУНКЦИЯ =====
def main():
    """Главная функция"""
    print("\n" + "="*60)
    print("🚀 ЗАПУСК БОТА")
    print("="*60)
    
    # Проверяем ключи
    print(f"\n📋 Наличие ключей:")
    print(f"   Gemini: {'✅' if GEMINI_KEY else '❌'} (библиотека: {'✅' if GEMINI_AVAILABLE else '❌'})")
    print(f"   Cerebras: {'✅' if CEREBRAS_KEY else '❌'}")
    print(f"   OpenRouter: {'✅' if OPENROUTER_KEY else '❌'}")
    
    # Получаем тип запуска
    run_type = os.environ.get('RUN_TYPE', 'unknown')
    print(f"📌 Тип запуска: {run_type}")
    
    # Время для логов
    current_hour = datetime.now().hour
    current_minute = datetime.now().minute
    print(f"🕐 Время UTC: {current_hour}:{current_minute}")
    print(f"🕐 Время МСК: {current_hour+3}:{current_minute}")
    
    # Проверяем текущую директорию
    print(f"📂 Текущая директория: {os.getcwd()}")
    print(f"📂 Содержимое: {os.listdir('.')}")
    
    sentence = None
    
    # ===== ЗАДАНИЕ =====
    if run_type == 'task':
        print("\n🔍 ГЕНЕРИРУЕМ НОВОЕ ПРЕДЛОЖЕНИЕ...")
        sentence = get_unique_ai_sentence()
        
        if not sentence:
            print("\n📚 Пробую базу...")
            sentence = get_unique_db_sentence()
        
        if not sentence:
            print("❌ НЕТ ПРЕДЛОЖЕНИЯ")
            return
        
        print(f"\n✅ ВЫБРАНО:")
        print(f"   🇬🇧 {sentence['en']}")
        print(f"   🇷🇺 {sentence['ru']}")
        
        # Сохраняем для ответа
        print("\n💾 Сохраняем предложение...")
        if save_last_sentence(sentence):
            print("✅ Предложение сохранено")
        else:
            print("⚠️ Не удалось сохранить, но продолжаем...")
        
        # Формируем сообщение
        message = f"📝 <b>ЕЖЕДНЕВНЫЙ ДИКТАНТ</b>\n\n"
        message += f"<b>Тема:</b> {sentence['topic']}\n"
        message += f"<b>Сложность:</b> {sentence.get('difficulty', 'легко')}\n\n"
        message += f"🇬🇧 <b>Переведи на русский:</b>\n"
        message += f"<i>{sentence['en']}</i>\n\n"
        message += f"⏳ <b>Ответ и разбор придут через 10 минут</b>"
        
        print("\n📨 Отправляем ЗАДАНИЕ...")
    
    # ===== ОТВЕТ =====
    elif run_type == 'answer':
        print("\n🔍 ЗАГРУЖАЕМ СОХРАНЕННОЕ ПРЕДЛОЖЕНИЕ...")
        sentence = load_last_sentence()
        
        if not sentence:
            print("⚠️ НЕТ СОХРАНЕННОГО ПРЕДЛОЖЕНИЯ, генерируем новое...")
            sentence = get_unique_ai_sentence()
            
            if not sentence:
                print("\n📚 Пробую базу...")
                sentence = get_unique_db_sentence()
            
            if not sentence:
                print("❌ НЕТ ПРЕДЛОЖЕНИЯ")
                return
            
            print(f"\n✅ СГЕНЕРИРОВАНО НОВОЕ:")
            print(f"   🇬🇧 {sentence['en']}")
            print(f"   🇷🇺 {sentence['ru']}")
        else:
            print(f"\n✅ ЗАГРУЖЕНО:")
            print(f"   🇬🇧 {sentence['en']}")
            print(f"   🇷🇺 {sentence['ru']}")
        
        # Формируем сообщение
        message = f"📝 <b>ПРОВЕРКА ДИКТАНТА</b>\n\n"
        message += f"🇬🇧 <b>Было:</b> {sentence['en']}\n"
        message += f"🇷🇺 <b>Правильный перевод:</b>\n"
        message += f"<i>{sentence['ru']}</i>\n\n"
        message += f"📊 <b>Грамматический разбор:</b>\n"
        message += f"{sentence.get('explanation', 'Продолжай практиковаться каждый день!')}\n\n"
        message += f"💪 Отличной работы!"
        
        print("\n📨 Отправляем ОТВЕТ...")
    
    else:
        print(f"❌ Неизвестный тип запуска: {run_type}")
        return
    
    # Отправляем сообщение
    result = send_telegram_message(message)
    
    if result:
        if run_type == 'task':
            # Помечаем как использованное только если это задание
            mark_as_used(sentence)
        print("\n✅ ВСЕ ОПЕРАЦИИ ВЫПОЛНЕНЫ УСПЕШНО")
    else:
        print("\n❌ НЕ УДАЛОСЬ ОТПРАВИТЬ СООБЩЕНИЕ")
    
    # Финальная проверка файлов
    print(f"\n📂 Финальное содержимое директории:")
    for f in os.listdir('.'):
        if f.endswith('.json') or f.endswith('.txt'):
            size = os.path.getsize(f) if os.path.exists(f) else 0
            print(f"   {f}: {size} байт")
    
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
