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

# ===== ОПРЕДЕЛЕНИЕ ТИПА ЗАПУСКА ПО ВРЕМЕНИ =====
def get_run_type():
    """Определяет, задание сейчас или ответ, строго по времени"""
    current_hour = datetime.now().hour
    current_minute = datetime.now().minute
    
    print(f"🕐 Текущее время UTC: {current_hour}:{current_minute:02d}")
    print(f"🕐 Текущее время МСК: {current_hour+3}:{current_minute:02d}")
    
    # ЗАДАНИЕ: 18:30-18:59 МСК (15:30-15:59 UTC)
    if current_hour == 15 and 30 <= current_minute < 60:
        print("📌 Режим: ЗАДАНИЕ")
        return 'task'
    
    # ОТВЕТ: 19:00-19:29 МСК (16:00-16:29 UTC)
    elif current_hour == 16 and 0 <= current_minute < 30:
        print("📌 Режим: ОТВЕТ")
        return 'answer'
    
    # Вне расписания - ничего не делаем
    else:
        print("📌 Режим: НЕ РАБОЧЕЕ ВРЕМЯ")
        return 'idle'

RUN_TYPE = get_run_type()

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
    """Загружает предложения из JSON"""
    try:
        with open(SENTENCES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data['sentences']
    except:
        return [
            {"id": 1, "en": "I like to read books in the evening", "ru": "Я люблю читать книги вечером", "topic": "📚 Хобби", "difficulty": "легко", "explanation": "Present Simple для выражения привычки. После I глагол без окончаний."},
            {"id": 2, "en": "She works as a doctor at the local hospital", "ru": "Она работает врачом в местной больнице", "topic": "💼 Работа", "difficulty": "легко", "explanation": "Present Simple. После she/he/it добавляем -s к глаголу."},
            {"id": 3, "en": "They are playing football in the park now", "ru": "Они сейчас играют в футбол в парке", "topic": "⚽ Спорт", "difficulty": "средне", "explanation": "Present Continuous (are + playing) для действия прямо сейчас."}
        ]

def load_used_ids():
    """Загружает список использованных ID"""
    try:
        if os.path.exists(USED_SENTENCES_FILE):
            with open(USED_SENTENCES_FILE, 'r') as f:
                content = f.read().strip()
                return set(map(int, content.split(','))) if content else set()
    except:
        pass
    return set()

def save_used_ids(used_ids):
    """Сохраняет список использованных ID"""
    with open(USED_SENTENCES_FILE, 'w') as f:
        f.write(','.join(map(str, used_ids)))

def mark_as_used(sentence):
    """Помечает предложение как использованное"""
    used_ids = load_used_ids()
    if 'id' not in sentence:
        text_hash = hashlib.md5(sentence['en'].encode()).hexdigest()[:8]
        sentence['id'] = int(text_hash, 16) % 1000000
    used_ids.add(sentence['id'])
    save_used_ids(used_ids)
    print(f"📝 Предложение помечено как использованное (ID: {sentence['id']})")

def is_used(sentence):
    """Проверяет, использовалось ли предложение"""
    used_ids = load_used_ids()
    if 'id' in sentence:
        return sentence['id'] in used_ids
    text_hash = hashlib.md5(sentence['en'].encode()).hexdigest()[:8]
    fake_id = int(text_hash, 16) % 1000000
    return fake_id in used_ids

# ===== СОХРАНЕНИЕ ПОСЛЕДНЕГО ПРЕДЛОЖЕНИЯ =====
def save_last_sentence(sentence):
    """Сохраняет последнее предложение для ответа"""
    with open(LAST_SENTENCE_FILE, 'w', encoding='utf-8') as f:
        json.dump(sentence, f, ensure_ascii=False, indent=2)
    print("✅ Последнее предложение сохранено")

def load_last_sentence():
    """Загружает последнее предложение для ответа"""
    if os.path.exists(LAST_SENTENCE_FILE):
        with open(LAST_SENTENCE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

# ===== ГЕНЕРАЦИЯ ЧЕРЕЗ GEMINI (ПРИОРИТЕТ 1) =====
def generate_with_gemini():
    """Генерация через Google Gemini"""
    if not GEMINI_AVAILABLE or not GEMINI_KEY:
        return None
    try:
        client = genai.Client(api_key=GEMINI_KEY)
        
        prompt = """Ты - профессиональный преподаватель английского языка. Создай учебное предложение для студентов.

Требования:
- Предложение должно быть из 5-10 слов
- Тема: повседневная жизнь (семья, работа, еда, путешествия, хобби, погода)
- Уровень: легкий или средний
- Грамматика: Present Simple, Present Continuous, Past Simple, Future Simple (выбирай разные)

Верни ТОЛЬКО JSON (без пояснений, без markdown):
{
    "en": "предложение на английском (5-10 слов)",
    "ru": "перевод на русский",
    "topic": "тема с эмодзи",
    "difficulty": "легко/средне",
    "explanation": "подробное объяснение грамматики на русском (2-3 предложения)"
}

Примеры хороших ответов:
{
    "en": "I usually drink coffee in the morning",
    "ru": "Я обычно пью кофе по утрам",
    "topic": "☕ Привычки",
    "difficulty": "легко",
    "explanation": "Present Simple для выражения привычки. Наречие usually стоит перед глаголом. После I глагол без окончаний."
}
{
    "en": "She is reading a book in the library now",
    "ru": "Она сейчас читает книгу в библиотеке",
    "topic": "📚 Образование",
    "difficulty": "средне",
    "explanation": "Present Continuous (is + reading) для действия, происходящего прямо сейчас. 'Now' указывает на момент речи."
}"""
        
        response = client.models.generate_content(
            model='models/gemini-1.5-flash',
            contents=prompt
        )
        
        if response and response.text:
            print(f"📝 Gemini ответ получен")
            sentence = extract_json(response.text)
            if sentence and all(k in sentence for k in ['en', 'ru', 'topic', 'explanation']):
                if len(sentence['en'].split()) >= 4:
                    return sentence
    except Exception as e:
        print(f"⚠️ Gemini ошибка: {type(e).__name__}")
    return None

# ===== ГЕНЕРАЦИЯ ЧЕРЕЗ CEREBRAS (ПРИОРИТЕТ 2) =====
def generate_with_cerebras():
    """Генерация через Cerebras"""
    if not CEREBRAS_KEY:
        return None
    try:
        prompt = """Ты - преподаватель английского языка. Создай учебное предложение.

Требования:
- Предложение должно быть из 5-10 слов
- Тема: повседневная жизнь (семья, работа, еда, хобби)
- Уровень: легкий или средний

Верни ТОЛЬКО JSON:
{
    "en": "предложение на английском (5-10 слов)",
    "ru": "перевод на русский",
    "topic": "тема с эмодзи",
    "difficulty": "легко/средне",
    "explanation": "короткое объяснение грамматики"
}

Пример:
{
    "en": "My sister works in a large company",
    "ru": "Моя сестра работает в большой компании",
    "topic": "💼 Работа",
    "difficulty": "легко",
    "explanation": "Present Simple для описания факта. После my sister (3 лицо) добавляем -s к глаголу work."
}"""
        
        response = requests.post(
            CEREBRAS_URL,
            headers={"Authorization": f"Bearer {CEREBRAS_KEY}", "Content-Type": "application/json"},
            json={
                "model": "llama3.3-70b",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.8,
                "max_tokens": 300
            },
            timeout=25
        )
        
        if response.status_code == 200:
            result = response.json()
            generated = result['choices'][0]['message']['content']
            print(f"📝 Cerebras ответ получен")
            
            sentence = extract_json(generated)
            if sentence and all(k in sentence for k in ['en', 'ru', 'topic', 'explanation']):
                if len(sentence['en'].split()) >= 4:
                    return sentence
    except Exception as e:
        print(f"⚠️ Cerebras ошибка: {type(e).__name__}")
    return None

# ===== ГЕНЕРАЦИЯ ЧЕРЕЗ OPENROUTER (ПРИОРИТЕТ 3) =====
def generate_with_openrouter():
    """Генерация через OpenRouter"""
    if not OPENROUTER_KEY:
        return None
    try:
        prompt = """Ты - учитель английского. Создай предложение.

Требования:
- Предложение из 5-10 слов
- Тема: повседневная жизнь

Верни JSON:
{
    "en": "предложение (5-10 слов)",
    "ru": "перевод",
    "topic": "тема",
    "difficulty": "легко/средне",
    "explanation": "объяснение"
}"""
        
        response = requests.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json"},
            json={
                "model": "openrouter/free",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.8,
                "max_tokens": 300
            },
            timeout=25
        )
        
        if response.status_code == 200:
            result = response.json()
            generated = result['choices'][0]['message']['content']
            print(f"📝 OpenRouter ответ получен")
            
            sentence = extract_json(generated)
            if sentence and all(k in sentence for k in ['en', 'ru', 'topic', 'explanation']):
                if len(sentence['en'].split()) >= 4:
                    return sentence
    except Exception as e:
        print(f"⚠️ OpenRouter ошибка: {type(e).__name__}")
    return None

# ===== ОСНОВНЫЕ ФУНКЦИИ =====
def get_unique_ai_sentence():
    """Пробует всех провайдеров в порядке приоритета"""
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
    
    used = load_used_ids()
    available = [s for s in sentences if s['id'] not in used]
    
    if not available:
        print("🔄 Все предложения использованы, начинаем заново")
        save_used_ids(set())
        available = sentences
    
    return random.choice(available)

def send_telegram_message(text):
    """Отправляет сообщение в Telegram"""
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ Нет BOT_TOKEN или CHAT_ID")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {
            'chat_id': CHAT_ID,
            'text': text,
            'parse_mode': 'HTML'
        }
        
        response = requests.post(url, data=data, timeout=10)
        
        if response.status_code == 200 and response.json().get('ok'):
            print("✅ Сообщение отправлено в Telegram")
            return True
        else:
            print(f"❌ Ошибка Telegram: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Ошибка отправки: {type(e).__name__}")
        return False

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
    
    # Если не рабочее время - выходим
    if RUN_TYPE == 'idle':
        print("⏰ Не рабочее время. Бот работает по расписанию:")
        print("   Задание: 18:30 - 19:00 МСК")
        print("   Ответ:   19:00 - 19:30 МСК")
        return
    
    # Логика: в task генерируем и сохраняем, в answer загружаем
    if RUN_TYPE == 'task':
        print("\n🔍 ГЕНЕРИРУЕМ НОВОЕ ПРЕДЛОЖЕНИЕ...")
        sentence = get_unique_ai_sentence()
        
        if not sentence:
            print("\n📚 Пробую базу...")
            sentence = get_unique_db_sentence()
        
        if not sentence:
            print("❌ НЕТ ПРЕДЛОЖЕНИЯ")
            return
        
        # Сохраняем для ответа и помечаем как использованное
        save_last_sentence(sentence)
        mark_as_used(sentence)
        
        print(f"\n✅ ВЫБРАНО:")
        print(f"   🇬🇧 {sentence['en']}")
        print(f"   🇷🇺 {sentence['ru']}")
        print(f"   📚 {sentence['topic']}")
        
        # Формируем сообщение
        message = f"📝 <b>ЕЖЕДНЕВНЫЙ ДИКТАНТ</b>\n\n"
        message += f"<b>Тема:</b> {sentence['topic']}\n"
        message += f"<b>Сложность:</b> {sentence.get('difficulty', 'легко')}\n\n"
        message += f"🇬🇧 <b>Переведи на русский:</b>\n"
        message += f"<i>{sentence['en']}</i>\n\n"
        message += f"⏳ <b>Ответ и разбор придут сегодня в 19:00</b>"
        
        print("\n📨 Отправляем ЗАДАНИЕ...")
        
    else:  # answer
        print("\n🔍 ЗАГРУЖАЕМ СОХРАНЕННОЕ ПРЕДЛОЖЕНИЕ...")
        sentence = load_last_sentence()
        
        if not sentence:
            print("⚠️ Нет сохранённого, генерируем новое...")
            sentence = get_unique_ai_sentence() or get_unique_db_sentence()
            if not sentence:
                print("❌ НЕТ ПРЕДЛОЖЕНИЯ")
                return
        
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
    
    # Отправляем сообщение
    if send_telegram_message(message):
        print("\n✅ ВСЕ ОПЕРАЦИИ ВЫПОЛНЕНЫ УСПЕШНО")
    else:
        print("\n❌ НЕ УДАЛОСЬ ОТПРАВИТЬ СООБЩЕНИЕ")
    
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
