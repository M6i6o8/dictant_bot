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

# ✅ ТОЛЬКО ПРОВЕРЕННЫЕ РАБОЧИЕ МОДЕЛИ (из теста)
WORKING_MODELS = [
    "openrouter/free",  # Роутер - выберет рабочую
    "arcee-ai/trinity-large-preview:free",
    "z-ai/glm-4.5-air:free"
]

# Запасные модели на случай, если основные упадут
BACKUP_MODELS = [
    "nvidia/nemotron-3-nano:free",
    "deepseek/deepseek-r1:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemma-3-27b-it:free"
]

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

def generate_with_openrouter():
    """Генерирует предложение используя ТОЛЬКО ПРОВЕРЕННЫЕ рабочие модели"""
    
    if not OPENROUTER_KEY:
        print("❌ Нет API ключа OpenRouter")
        return None
    
    # Пробуем сначала основные рабочие модели
    models_to_try = WORKING_MODELS + BACKUP_MODELS
    
    for model in models_to_try:
        print(f"🤖 Пробую модель: {model}")
        
        prompt = """Ты - помощник для изучения английского языка. 
        Сгенерируй простое предложение на английском с переводом на русский.
        
        Требования:
        - Предложение из 5-10 слов
        - Тема: повседневная жизнь (семья, работа, еда, путешествия, хобби)
        - Уровень: легкий
        
        Верни ТОЛЬКО JSON:
        {
            "en": "предложение на английском",
            "ru": "перевод на русский",
            "topic": "тема с эмодзи",
            "difficulty": "легко"
        }
        
        Пример: {"en": "I like to drink coffee", "ru": "Я люблю пить кофе", "topic": "☕ Еда", "difficulty": "легко"}
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
                timeout=20
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
                        print(f"✅ Успешно сгенерировано моделью {actual_model}")
                        return sentence
                    else:
                        print(f"⚠️ Модель вернула неполные данные, пробуем следующую...")
                else:
                    print(f"⚠️ Модель не вернула JSON, пробуем следующую...")
            else:
                print(f"⚠️ Ошибка {response.status_code}, пробуем следующую...")
                
        except Exception as e:
            print(f"⚠️ Ошибка с моделью {model}: {type(e).__name__}, пробуем следующую...")
            continue
    
    print("❌ Ни одна модель не сработала")
    return None

def get_unique_ai_sentence(max_attempts=2):
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
    print("🚀 ЗАПУСК БОТА (ПРОВЕРЕННЫЕ МОДЕЛИ)")
    print("="*50)
    
    # Проверяем ключи
    print(f"🤖 BOT_TOKEN: {'✅' if BOT_TOKEN else '❌'}")
    print(f"📢 CHAT_ID: {'✅' if CHAT_ID else '❌'}")
    print(f"🔑 OPENROUTER_KEY: {'✅' if OPENROUTER_KEY else '❌'}")
    
    print("\n📋 Используемые модели:")
    for m in WORKING_MODELS:
        print(f"   ✅ {m}")
    
    current_hour = datetime.now().hour
    print(f"🕐 Текущее время UTC: {current_hour}:{datetime.now().minute}")
    
    # Для теста игнорируем время
    # if current_hour not in [6, 7]:
    #     print("⏰ Не время для отправки")
    #     return
    
    print("\n🔍 ИЩЕМ УНИКАЛЬНОЕ ПРЕДЛОЖЕНИЕ...")
    
    sentence = None
    
    # Пробуем AI
    if OPENROUTER_KEY:
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
