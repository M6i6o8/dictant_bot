import json
import random
import os
import requests
import hashlib
import re
from datetime import datetime, timedelta
import subprocess

# Google Gemini
try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

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

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====
def get_msk_date():
    """Возвращает сегодняшнюю дату по московскому времени"""
    msk_time = datetime.utcnow() + timedelta(hours=3)
    return msk_time.strftime('%Y-%m-%d')

def get_msk_datetime():
    """Возвращает полное время по МСК"""
    return datetime.utcnow() + timedelta(hours=3)

# ===== ТИП ЗАПУСКА ИЗ ПЕРЕМЕННОЙ ОКРУЖЕНИЯ =====
RUN_TYPE = os.environ.get('RUN_TYPE', 'unknown')
print(f"\n📌 Тип запуска из GitHub: {RUN_TYPE}")
print(f"🕐 Время по МСК: {get_msk_datetime().strftime('%Y-%m-%d %H:%M:%S')}")

# ===== ФУНКЦИИ РАБОТЫ С ФАЙЛАМИ =====
def load_used_ids():
    try:
        if os.path.exists(USED_SENTENCES_FILE):
            with open(USED_SENTENCES_FILE, 'r') as f:
                content = f.read().strip()
                return set(map(int, content.split(','))) if content else set()
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
    print(f"✅ ID {sentence['id']} добавлен в used_sentences.txt")

def is_used(sentence):
    used_ids = load_used_ids()
    if 'id' in sentence:
        return sentence['id'] in used_ids
    return False

def save_last_sentence(sentence):
    try:
        with open(LAST_SENTENCE_FILE, 'w', encoding='utf-8') as f:
            json.dump(sentence, f, ensure_ascii=False, indent=2)
        print(f"✅ Предложение сохранено в {LAST_SENTENCE_FILE}")
        return True
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")
        return False

def load_last_sentence():
    try:
        if os.path.exists(LAST_SENTENCE_FILE):
            with open(LAST_SENTENCE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"❌ Ошибка загрузки: {e}")
    return None

def was_task_sent_today():
    return os.path.exists(LAST_SENTENCE_FILE)

def is_answer_sent_today():
    """Проверка, отправлен ли ответ сегодня (по МСК)"""
    if os.path.exists(ANSWER_SENT_FILE):
        with open(ANSWER_SENT_FILE, 'r') as f:
            last_date = f.read().strip()
            today = get_msk_date()
            print(f"📅 Последний ответ в файле: {last_date}")
            print(f"📅 Сегодня по МСК: {today}")
            
            # Если даты совпадают - ответ уже был
            if last_date == today:
                print("✅ Ответ сегодня уже был")
                return True
            else:
                print("📅 Ответ был в другой день")
                return False
    print("📁 Файл answer_sent.txt не найден")
    return False

def mark_answer_sent():
    """Отмечает, что ответ отправлен (по МСК)"""
    today = get_msk_date()
    with open(ANSWER_SENT_FILE, 'w') as f:
        f.write(today)
    print(f"✅ Ответ отмечен по МСК: {today}")
    
    # Дополнительная проверка
    if os.path.exists(ANSWER_SENT_FILE):
        with open(ANSWER_SENT_FILE, 'r') as f:
            written = f.read().strip()
            print(f"📝 Проверка записи: {written}")

# ===== ИЗВЛЕКАТЕЛЬ JSON =====
def extract_json(text):
    if not text:
        return None
    
    text = text.replace('```json', '').replace('```', '').strip()
    json_pattern = r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}'
    matches = re.findall(json_pattern, text)
    
    for json_str in matches:
        try:
            return json.loads(json_str)
        except:
            try:
                return json.loads(json_str.replace("'", '"'))
            except:
                continue
    return None

# ===== ГЕНЕРАЦИЯ =====
def generate_with_gemini():
    if not GEMINI_AVAILABLE or not GEMINI_KEY:
        return None
    try:
        client = genai.Client(api_key=GEMINI_KEY)
        prompt = """Создай простое учебное предложение на английском для ежедневной практики перевода.
Тема: повседневная жизнь, семья, работа, путешествия, хобби, еда.
Уровень: легкий или средний.

Верни ТОЛЬКО JSON:
{
    "en": "предложение на английском (5-10 слов)",
    "ru": "перевод на русский",
    "topic": "тема с эмодзи",
    "difficulty": "легко/средне",
    "explanation": "объяснение грамматики на русском"
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

def generate_with_cerebras():
    if not CEREBRAS_KEY:
        return None
    try:
        response = requests.post(
            CEREBRAS_URL,
            headers={"Authorization": f"Bearer {CEREBRAS_KEY}"},
            json={
                "model": "llama3.3-70b",
                "messages": [{"role": "user", "content": """Создай JSON для изучения английского:
{"en": "I usually drink coffee in the morning", "ru": "Я обычно пью кофе по утрам", "topic": "☕ Привычки", "difficulty": "легко", "explanation": "Present Simple для выражения привычки"}"""}],
                "temperature": 0.8
            },
            timeout=15
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
                "messages": [{"role": "user", "content": """Создай JSON с английским предложением и переводом.
Пример: {"en": "My sister works in a hospital", "ru": "Моя сестра работает в больнице", "topic": "💼 Работа", "difficulty": "легко", "explanation": "Present Simple для фактов"}"""}]
            },
            timeout=15
        )
        if response.status_code == 200:
            return extract_json(response.json()['choices'][0]['message']['content'])
    except:
        return None

def get_unique_sentence():
    providers = [
        ("Gemini", generate_with_gemini),
        ("Cerebras", generate_with_cerebras),
        ("OpenRouter", generate_with_openrouter)
    ]
    
    for name, func in providers:
        print(f"\n🤖 Пробую {name}...")
        s = func()
        if s and all(k in s for k in ['en', 'ru', 'topic']):
            if not is_used(s):
                print(f"✅ {name} сработал!")
                return s
            else:
                print(f"⚠️ Предложение уже использовалось")
    return None

def send_telegram_message(text):
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

def commit_and_push_files():
    """Коммитит изменения в репозиторий"""
    files_to_commit = []
    for f in [LAST_SENTENCE_FILE, USED_SENTENCES_FILE, ANSWER_SENT_FILE]:
        if os.path.exists(f):
            files_to_commit.append(f)
    
    if not files_to_commit:
        return
    
    try:
        subprocess.run(['git', 'config', '--global', 'user.name', 'github-actions[bot]'], check=True)
        subprocess.run(['git', 'config', '--global', 'user.email', 'github-actions[bot]@users.noreply.github.com'], check=True)
        subprocess.run(['git', 'add'] + files_to_commit, check=True)
        subprocess.run(['git', 'commit', '-m', f'[bot] Update state files {get_msk_date()}'], check=True)
        subprocess.run(['git', 'push'], check=True)
        print("✅ Изменения закоммичены")
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Ошибка коммита (возможно, нечего коммитить): {e}")

# ===== ГЛАВНАЯ =====
def main():
    print("\n" + "="*50)
    print("🚀 ЗАПУСК БОТА")
    print("="*50)
    
    print(f"🤖 BOT_TOKEN: {'✅' if BOT_TOKEN else '❌'}")
    print(f"📢 CHAT_ID: {'✅' if CHAT_ID else '❌'}")
    print(f"🔑 GEMINI_KEY: {'✅' if GEMINI_KEY else '❌'}")
    print(f"🔑 CEREBRAS_KEY: {'✅' if CEREBRAS_KEY else '❌'}")
    print(f"🔑 OPENROUTER_KEY: {'✅' if OPENROUTER_KEY else '❌'}")
    
    if RUN_TYPE == 'task':
        print("\n🔍 ГЕНЕРИРУЮ ЗАДАНИЕ...")
        s = get_unique_sentence()
        
        if not s:
            print("❌ Нет предложения")
            return
        
        save_last_sentence(s)
        mark_as_used(s)
        
        # Получаем час и минуту ответа из времени запуска +10 минут
        answer_time = get_msk_datetime() + timedelta(minutes=10)
        answer_time_str = answer_time.strftime('%H:%M')
        
        msg = f"📝 <b>ЕЖЕДНЕВНЫЙ ДИКТАНТ</b>\n\n"
        msg += f"<b>Тема:</b> {s['topic']}\n"
        msg += f"<b>Сложность:</b> {s.get('difficulty', 'легко')}\n\n"
        msg += f"🇬🇧 <b>Переведи на русский:</b>\n"
        msg += f"<i>{s['en']}</i>\n\n"
        msg += f"⏳ <b>Ответ и разбор придут сегодня в {answer_time_str}</b>"
        
        if send_telegram_message(msg):
            print("\n✅ ЗАДАНИЕ ОТПРАВЛЕНО")
            commit_and_push_files()
    
    elif RUN_TYPE == 'answer':
        print("\n🔍 ПРОВЕРЯЮ ЗАДАНИЕ...")
        
        if not was_task_sent_today():
            print("❌ Нет задания")
            return
        
        if is_answer_sent_today():
            print("✅ Ответ уже был")
            return
        
        s = load_last_sentence()
        if not s:
            print("❌ Ошибка загрузки")
            return
        
        msg = f"📝 <b>ПРОВЕРКА ДИКТАНТА</b>\n\n"
        msg += f"🇬🇧 <b>Было:</b> {s['en']}\n"
        msg += f"🇷🇺 <b>Правильный перевод:</b>\n"
        msg += f"<i>{s['ru']}</i>\n\n"
        msg += f"📊 <b>Разбор:</b>\n"
        msg += f"{s.get('explanation', 'Продолжай практиковаться каждый день!')}"
        
        if send_telegram_message(msg):
            mark_answer_sent()
            print("\n✅ ОТВЕТ ОТПРАВЛЕН")
            commit_and_push_files()
    
    else:
        print(f"❌ Неизвестный тип запуска: {RUN_TYPE}")
    
    print("="*50)

if __name__ == "__main__":
    main()
