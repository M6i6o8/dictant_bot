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
ANSWER_SENT_FILE = 'answer_sent.txt'

OPENROUTER_KEY = os.environ.get('OPENROUTER_KEY')
GEMINI_KEY = os.environ.get('GEMINI_KEY')
CEREBRAS_KEY = os.environ.get('CEREBRAS_KEY')

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
CEREBRAS_URL = "https://api.cerebras.ai/v1/chat/completions"

# ===== НАСТРОЙКА ВРЕМЕНИ (МЕНЯЙ ТОЛЬКО ЗДЕСЬ!) =====
TASK_HOUR_MSK = 10        # Час задания по Москве
TASK_MINUTE_MSK = 30      # Минута задания
ANSWER_HOUR_MSK = 11      # Час ответа по Москве
ANSWER_MINUTE_MSK = 0     # Минута ответа

# Автоматический пересчёт в UTC (МСК = UTC + 3)
TASK_HOUR_UTC = TASK_HOUR_MSK - 3
ANSWER_HOUR_UTC = ANSWER_HOUR_MSK - 3

# Корректировка для отрицательных часов
if TASK_HOUR_UTC < 0:
    TASK_HOUR_UTC += 24
if ANSWER_HOUR_UTC < 0:
    ANSWER_HOUR_UTC += 24

print(f"\n⚙️ НАСТРОЙКИ ВРЕМЕНИ:")
print(f"   Задание: {TASK_HOUR_MSK:02d}:{TASK_MINUTE_MSK:02d} МСК = {TASK_HOUR_UTC:02d}:{TASK_MINUTE_MSK:02d} UTC")
print(f"   Ответ:   {ANSWER_HOUR_MSK:02d}:{ANSWER_MINUTE_MSK:02d} МСК = {ANSWER_HOUR_UTC:02d}:{ANSWER_MINUTE_MSK:02d} UTC")

# ===== ФУНКЦИИ ПРОВЕРКИ =====
def was_task_sent_today():
    """Проверяет, было ли отправлено задание сегодня"""
    if not os.path.exists(LAST_SENTENCE_FILE):
        print("📁 Файл last_sentence.json не найден")
        return False
    
    try:
        with open(LAST_SENTENCE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if data and 'en' in data:
            print(f"✅ Задание найдено в файле: {data['en'][:50]}...")
            return True
        else:
            print("⚠️ Файл есть, но он пустой")
            return False
    except Exception as e:
        print(f"❌ Ошибка чтения файла: {e}")
        return False

def is_answer_sent_today():
    """Проверяет, отправлен ли уже ответ сегодня"""
    if os.path.exists(ANSWER_SENT_FILE):
        with open(ANSWER_SENT_FILE, 'r') as f:
            last_date = f.read().strip()
            today = datetime.now().strftime('%Y-%m-%d')
            return last_date == today
    return False

def mark_answer_sent():
    """Отмечает, что ответ отправлен сегодня"""
    with open(ANSWER_SENT_FILE, 'w') as f:
        f.write(datetime.now().strftime('%Y-%m-%d'))
    print("✅ Отметка об ответе сохранена")

# ===== ОПРЕДЕЛЕНИЕ ТИПА ЗАПУСКА =====
def get_run_type():
    """Определяет, задание сейчас или ответ"""
    current_hour = datetime.now().hour
    current_minute = datetime.now().minute
    
    print(f"\n🕐 Текущее время UTC: {current_hour}:{current_minute:02d}")
    print(f"🕐 Текущее время МСК: {current_hour+3}:{current_minute:02d}")
    
    # Задание: 30 минут после TASK_HOUR_UTC
    if current_hour == TASK_HOUR_UTC and TASK_MINUTE_MSK <= current_minute < TASK_MINUTE_MSK + 30:
        print("📌 Режим: ЗАДАНИЕ")
        return 'task'
    
    # Ответ: 30 минут после ANSWER_HOUR_UTC
    if current_hour == ANSWER_HOUR_UTC and ANSWER_MINUTE_MSK <= current_minute < ANSWER_MINUTE_MSK + 30:
        print("📌 Режим: ОТВЕТ")
        return 'answer'
    
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
            {"id": 1, "en": "I like to read books in the evening", "ru": "Я люблю читать книги вечером", "topic": "📚 Хобби", "difficulty": "легко", "explanation": "Present Simple для выражения привычки."},
            {"id": 2, "en": "She works as a doctor at the local hospital", "ru": "Она работает врачом", "topic": "💼 Работа", "difficulty": "легко", "explanation": "Present Simple. После she добавляем -s."},
            {"id": 3, "en": "They are playing football in the park now", "ru": "Они играют в футбол", "topic": "⚽ Спорт", "difficulty": "средне", "explanation": "Present Continuous для действия прямо сейчас."}
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
    try:
        with open(LAST_SENTENCE_FILE, 'w', encoding='utf-8') as f:
            json.dump(sentence, f, ensure_ascii=False, indent=2)
        print(f"✅ Предложение сохранено в {LAST_SENTENCE_FILE}")
        
        # Проверяем, что сохранилось
        if os.path.exists(LAST_SENTENCE_FILE):
            size = os.path.getsize(LAST_SENTENCE_FILE)
            print(f"   Размер файла: {size} байт")
        return True
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")
        return False

def load_last_sentence():
    """Загружает последнее предложение для ответа"""
    try:
        if os.path.exists(LAST_SENTENCE_FILE):
            with open(LAST_SENTENCE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"✅ Предложение загружено из {LAST_SENTENCE_FILE}")
                return data
        else:
            print(f"⚠️ Файл {LAST_SENTENCE_FILE} не найден")
    except Exception as e:
        print(f"❌ Ошибка загрузки: {e}")
    return None

# ===== ГЕНЕРАЦИЯ ЧЕРЕЗ GEMINI =====
def generate_with_gemini():
    if not GEMINI_AVAILABLE or not GEMINI_KEY:
        return None
    try:
        client = genai.Client(api_key=GEMINI_KEY)
        
        prompt = """Ты - преподаватель английского. Создай учебное предложение.
        
        Верни ТОЛЬКО JSON:
        {
            "en": "предложение на английском (5-10 слов)",
            "ru": "перевод на русский",
            "topic": "тема с эмодзи",
            "difficulty": "легко/средне",
            "explanation": "объяснение грамматики"
        }"""
        
        response = client.models.generate_content(
            model='models/gemini-1.5-flash',
            contents=prompt
        )
        
        if response and response.text:
            return extract_json(response.text)
    except Exception as e:
        print(f"⚠️ Gemini ошибка: {type(e).__name__}")
    return None

# ===== ГЕНЕРАЦИЯ ЧЕРЕЗ CEREBRAS =====
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

# ===== ГЕНЕРАЦИЯ ЧЕРЕЗ OPENROUTER =====
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

# ===== ФУНКЦИЯ РАЗБОРА =====
def generate_fallback_explanation(sentence):
    """Создаёт разбор, если AI не дал"""
    explanation = sentence.get('explanation', '')
    
    if not explanation or explanation == "Продолжай практиковаться каждый день!":
        text = sentence['en']
        words = len(text.split())
        
        if 'ing' in text and ('am' in text or 'is' in text or 'are' in text):
            return f"Present Continuous: действие происходит прямо сейчас. В предложении {words} слов."
        elif 'have' in text.lower() or 'has' in text.lower():
            return f"Perfect время: действие связано с настоящим. В предложении {words} слов."
        elif 'will' in text.lower():
            return f"Future Simple: будущее действие. В предложении {words} слов."
        elif 'ed ' in text or text.lower().endswith('ed'):
            return f"Past Simple: действие в прошлом. В предложении {words} слов."
        else:
            return f"Present Simple: факт или привычка. В предложении {words} слов."
    
    return explanation

# ===== ОСНОВНЫЕ ФУНКЦИИ =====
def get_unique_ai_sentence():
    providers = [
        ("Gemini", generate_with_gemini),
        ("Cerebras", generate_with_cerebras),
        ("OpenRouter", generate_with_openrouter)
    ]
    
    for name, func in providers:
        print(f"\n🤖 Пробую {name}...")
        sentence = func()
        if sentence:
            if all(k in sentence for k in ['en', 'ru', 'topic']):
                if 'explanation' not in sentence:
                    sentence['explanation'] = ""
                if not is_used(sentence):
                    print(f"✅ {name} сработал!")
                    return sentence
    return None

def get_unique_db_sentence():
    sentences = load_sentences()
    if not sentences:
        return None
    
    used = load_used_ids()
    available = [s for s in sentences if s['id'] not in used]
    
    if not available:
        save_used_ids(set())
        available = sentences
    
    return random.choice(available)

def send_telegram_message(text):
    if not BOT_TOKEN or not CHAT_ID:
        return False
    
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={'chat_id': CHAT_ID, 'text': text, 'parse_mode': 'HTML'},
            timeout=10
        )
        if response.status_code == 200 and response.json().get('ok'):
            print("✅ Сообщение отправлено в Telegram")
            return True
    except Exception as e:
        print(f"❌ Ошибка отправки: {type(e).__name__}")
    return False

# ===== ГЛАВНАЯ ФУНКЦИЯ =====
def main():
    print("\n" + "="*60)
    print("🚀 ЗАПУСК БОТА")
    print("="*60)
    
    print(f"\n📋 Наличие ключей:")
    print(f"   Gemini: {'✅' if GEMINI_KEY else '❌'}")
    print(f"   Cerebras: {'✅' if CEREBRAS_KEY else '❌'}")
    print(f"   OpenRouter: {'✅' if OPENROUTER_KEY else '❌'}")
    
    if RUN_TYPE == 'idle':
        print(f"\n⏰ Не рабочее время. Бот работает:")
        print(f"   Задание: {TASK_HOUR_MSK:02d}:{TASK_MINUTE_MSK:02d} - {TASK_HOUR_MSK:02d}:{TASK_MINUTE_MSK+30:02d}")
        print(f"   Ответ:   {ANSWER_HOUR_MSK:02d}:{ANSWER_MINUTE_MSK:02d} - {ANSWER_HOUR_MSK:02d}:{ANSWER_MINUTE_MSK+30:02d}")
        return
    
    if RUN_TYPE == 'task':
        print("\n🔍 ГЕНЕРИРУЕМ НОВОЕ ПРЕДЛОЖЕНИЕ...")
        sentence = get_unique_ai_sentence()
        
        if not sentence:
            print("\n📚 Пробую базу...")
            sentence = get_unique_db_sentence()
        
        if not sentence:
            print("❌ НЕТ ПРЕДЛОЖЕНИЯ")
            return
        
        # СОХРАНЯЕМ С ФОРСИРОВАННОЙ ПРОВЕРКОЙ
        print("\n💾 СОХРАНЯЕМ ПРЕДЛОЖЕНИЕ...")
        save_result = save_last_sentence(sentence)
        
        if not save_result:
            print("⚠️ Повторная попытка сохранения...")
            save_last_sentence(sentence)
        
        mark_as_used(sentence)
        
        print(f"\n✅ ВЫБРАНО:")
        print(f"   🇬🇧 {sentence['en']}")
        print(f"   🇷🇺 {sentence['ru']}")
        
        message = f"📝 <b>ЕЖЕДНЕВНЫЙ ДИКТАНТ</b>\n\n"
        message += f"<b>Тема:</b> {sentence['topic']}\n"
        message += f"<b>Сложность:</b> {sentence.get('difficulty', 'легко')}\n\n"
        message += f"🇬🇧 <b>Переведи на русский:</b>\n"
        message += f"<i>{sentence['en']}</i>\n\n"
        message += f"⏳ <b>Ответ и разбор придут сегодня в {ANSWER_HOUR_MSK:02d}:{ANSWER_MINUTE_MSK:02d}</b>"
        
        print("\n📨 Отправляем ЗАДАНИЕ...")
        
        if send_telegram_message(message):
            print("\n✅ ВСЁ ГОТОВО")
        else:
            print("\n❌ ОШИБКА ОТПРАВКИ")
    
    else:  # answer
        print("\n🔍 ПРОВЕРЯЕМ НАЛИЧИЕ ЗАДАНИЯ...")
        
        if not was_task_sent_today():
            print("❌ Задание не найдено, ответ не отправляем")
            return
        
        if is_answer_sent_today():
            print("✅ Ответ уже был отправлен сегодня")
            return
        
        print("\n🔍 ЗАГРУЖАЕМ ПРЕДЛОЖЕНИЕ...")
        sentence = load_last_sentence()
        
        if not sentence:
            print("❌ НЕ УДАЛОСЬ ЗАГРУЗИТЬ ПРЕДЛОЖЕНИЕ")
            return
        
        explanation = generate_fallback_explanation(sentence)
        
        message = f"📝 <b>ПРОВЕРКА ДИКТАНТА</b>\n\n"
        message += f"🇬🇧 <b>Было:</b> {sentence['en']}\n"
        message += f"🇷🇺 <b>Правильный перевод:</b>\n"
        message += f"<i>{sentence['ru']}</i>\n\n"
        message += f"📊 <b>Грамматический разбор:</b>\n"
        message += f"{explanation}\n\n"
        message += f"💪 Отличной работы!"
        
        print("\n📨 Отправляем ОТВЕТ...")
        
        if send_telegram_message(message):
            mark_answer_sent()
            print("\n✅ ВСЁ ГОТОВО")
        else:
            print("\n❌ ОШИБКА ОТПРАВКИ")
    
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
