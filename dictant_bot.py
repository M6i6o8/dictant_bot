import json
import random
import os
import requests
import hashlib
import re
from datetime import datetime
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

# ===== НАСТРОЙКА ВРЕМЕНИ =====
TASK_HOUR_MSK = 18
TASK_MINUTE_MSK = 32
ANSWER_HOUR_MSK = 19
ANSWER_MINUTE_MSK = 2

TASK_HOUR_UTC = TASK_HOUR_MSK - 3
ANSWER_HOUR_UTC = ANSWER_HOUR_MSK - 3

if TASK_HOUR_UTC < 0:
    TASK_HOUR_UTC += 24
if ANSWER_HOUR_UTC < 0:
    ANSWER_HOUR_UTC += 24

print(f"\n⚙️ ЗАДАНИЕ: {TASK_HOUR_MSK:02d}:{TASK_MINUTE_MSK:02d} МСК = {TASK_HOUR_UTC:02d}:{TASK_MINUTE_MSK:02d} UTC")
print(f"⚙️ ОТВЕТ:   {ANSWER_HOUR_MSK:02d}:{ANSWER_MINUTE_MSK:02d} МСК = {ANSWER_HOUR_UTC:02d}:{ANSWER_MINUTE_MSK:02d} UTC")

# ===== ПРОВЕРКА ФАЙЛОВ =====
print(f"\n📁 Файлы перед запуском:")
print(f"   last_sentence.json: {'✅' if os.path.exists(LAST_SENTENCE_FILE) else '❌'}")
print(f"   used_sentences.txt: {'✅' if os.path.exists(USED_SENTENCES_FILE) else '❌'}")
print(f"   answer_sent.txt: {'✅' if os.path.exists(ANSWER_SENT_FILE) else '❌'}")

# ===== ОПРЕДЕЛЕНИЕ ТИПА ЗАПУСКА =====
def get_run_type():
    current_hour = datetime.now().hour
    current_minute = datetime.now().minute

    print(f"\n🕐 UTC: {current_hour}:{current_minute:02d}")
    print(f"🕐 МСК: {current_hour+3}:{current_minute:02d}")

    if current_hour == TASK_HOUR_UTC and TASK_MINUTE_MSK <= current_minute < TASK_MINUTE_MSK + 30:
        print("📌 Режим: ЗАДАНИЕ")
        return 'task'
    if current_hour == ANSWER_HOUR_UTC and ANSWER_MINUTE_MSK <= current_minute < ANSWER_MINUTE_MSK + 30:
        print("📌 Режим: ОТВЕТ")
        return 'answer'
    print("📌 Режим: НЕ РАБОЧЕЕ ВРЕМЯ")
    return 'idle'

RUN_TYPE = get_run_type()

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
    if os.path.exists(ANSWER_SENT_FILE):
        with open(ANSWER_SENT_FILE, 'r') as f:
            return f.read().strip() == datetime.now().strftime('%Y-%m-%d')
    return False

def mark_answer_sent():
    with open(ANSWER_SENT_FILE, 'w') as f:
        f.write(datetime.now().strftime('%Y-%m-%d'))
    print("✅ Ответ отмечен как отправленный")

def commit_and_push_files():
    """Коммитит и пушит изменения файлов обратно в репозиторий"""
    files_to_commit = []
    if os.path.exists(LAST_SENTENCE_FILE):
        files_to_commit.append(LAST_SENTENCE_FILE)
    if os.path.exists(USED_SENTENCES_FILE):
        files_to_commit.append(USED_SENTENCES_FILE)
    if os.path.exists(ANSWER_SENT_FILE):
        files_to_commit.append(ANSWER_SENT_FILE)

    if not files_to_commit:
        return

    try:
        subprocess.run(['git', 'config', '--global', 'user.name', 'github-actions[bot]'], check=True)
        subprocess.run(['git', 'config', '--global', 'user.email', 'github-actions[bot]@users.noreply.github.com'], check=True)
        subprocess.run(['git', 'add'] + files_to_commit, check=True)
        subprocess.run(['git', 'commit', '-m', '[bot] Update state files'], check=True)
        subprocess.run(['git', 'push'], check=True)
        print("✅ Изменения закоммичены и отправлены в репозиторий")
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Ошибка при коммите/пуше (возможно, нечего коммитить): {e}")

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
        else:
            print(f"❌ Ошибка Telegram: {response.status_code}")
    except Exception as e:
        print(f"❌ Ошибка отправки: {type(e).__name__}")
    return False

# ===== ГЛАВНАЯ =====
def main():
    print("\n" + "="*50)
    print("🚀 ЗАПУСК БОТА")
    print("="*50)

    if RUN_TYPE == 'idle':
        print("⏰ Не рабочее время")
        print("="*50)
        return

    if RUN_TYPE == 'task':
        print("\n🔍 ГЕНЕРИРУЮ ЗАДАНИЕ...")
        s = get_unique_sentence()

        if not s:
            print("❌ Не удалось получить предложение")
            print("="*50)
            return

        save_last_sentence(s)
        mark_as_used(s)

        msg = f"📝 <b>ЕЖЕДНЕВНЫЙ ДИКТАНТ</b>\n\n"
        msg += f"<b>Тема:</b> {s['topic']}\n"
        msg += f"<b>Сложность:</b> {s.get('difficulty', 'легко')}\n\n"
        msg += f"🇬🇧 <b>Переведи на русский:</b>\n"
        msg += f"<i>{s['en']}</i>\n\n"
        msg += f"⏳ <b>Ответ и разбор придут сегодня в {ANSWER_HOUR_MSK:02d}:{ANSWER_MINUTE_MSK:02d}</b>"

        if send_telegram_message(msg):
            print("\n✅ ЗАДАНИЕ ОТПРАВЛЕНО")
            # КОММИТИМ ПОСЛЕ УСПЕШНОЙ ОТПРАВКИ
            commit_and_push_files()
        else:
            print("\n❌ ОШИБКА ОТПРАВКИ")

    else:  # answer
        print("\n🔍 ПРОВЕРЯЮ ЗАДАНИЕ...")

        if not was_task_sent_today():
            print("❌ Задание не найдено, ответ не отправляю")
            print("="*50)
            return

        if is_answer_sent_today():
            print("✅ Ответ уже был отправлен сегодня")
            print("="*50)
            return

        print("\n🔍 ЗАГРУЖАЮ ПРЕДЛОЖЕНИЕ...")
        s = load_last_sentence()

        if not s:
            print("❌ Не удалось загрузить предложение")
            print("="*50)
            return

        explanation = s.get('explanation', 'Продолжай практиковаться каждый день!')

        msg = f"📝 <b>ПРОВЕРКА ДИКТАНТА</b>\n\n"
        msg += f"🇬🇧 <b>Было:</b> {s['en']}\n"
        msg += f"🇷🇺 <b>Правильный перевод:</b>\n"
        msg += f"<i>{s['ru']}</i>\n\n"
        msg += f"📊 <b>Грамматический разбор:</b>\n"
        msg += f"{explanation}\n\n"
        msg += f"💪 Отличной работы!"

        if send_telegram_message(msg):
            mark_answer_sent()
            print("\n✅ ОТВЕТ ОТПРАВЛЕН")
            # КОММИТИМ ПОСЛЕ УСПЕШНОЙ ОТПРАВКИ
            commit_and_push_files()
        else:
            print("\n❌ ОШИБКА ОТПРАВКИ")

    print("="*50)

if __name__ == "__main__":
    main()



