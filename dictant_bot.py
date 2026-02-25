import json
import random
import os
import requests
import time
from datetime import datetime

# ===== НАСТРОЙКИ =====
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
SENTENCES_FILE = 'sentences.json'

def load_sentences():
    """Загружает предложения из JSON"""
    try:
        with open(SENTENCES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data['sentences']
    except Exception as e:
        print(f"Ошибка загрузки sentences.json: {e}")
        # Аварийный вариант
        return [
            {
                "id": 1,
                "en": "I bought a new car yesterday",
                "ru": "Я вчера купил новую машину",
                "topic": "🚗 Покупки",
                "difficulty": "легко"
            }
        ]

def load_last_sentence():
    """Загружает ID последнего предложения"""
    try:
        if os.path.exists('last_sentence.txt'):
            with open('last_sentence.txt', 'r') as f:
                content = f.read().strip()
                if content:
                    return int(content)
        return None
    except Exception as e:
        print(f"Ошибка чтения файла: {e}")
        return None

def save_last_sentence(sentence_id):
    """Сохраняет ID последнего предложения"""
    try:
        with open('last_sentence.txt', 'w') as f:
            f.write(str(sentence_id))
        print(f"✅ Сохранен ID: {sentence_id}")
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")

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
    print("🚀 Запуск...")
    
    # Проверяем время (UTC)
    current_hour = datetime.now().hour
    print(f"🕐 Текущий час UTC: {current_hour}")
    
    # Загружаем предложения
    sentences = load_sentences()
    last_id = load_last_sentence()
    
    # Выбираем предложение (не повторяем последнее)
    available = [s for s in sentences if s['id'] != last_id]
    if not available:
        available = sentences
    sentence = random.choice(available)
    print(f"🎯 Выбрано предложение ID: {sentence['id']}")
    
    # Отправляем в зависимости от времени
    if current_hour == 6:  # 9:00 МСК
        message = f"📝 <b>Ежедневный диктант</b>\n\n"
        message += f"<b>Тема:</b> {sentence['topic']}\n"
        message += f"<b>Сложность:</b> {sentence['difficulty']}\n\n"
        message += f"🇬🇧 <b>Переведи на русский:</b>\n"
        message += f"<i>{sentence['en']}</i>\n\n"
        message += f"⏳ <b>Ответ придет в 10:00</b>\n"
        message += f"✍️ Пиши свой вариант в комментарии!"
        
        result = send_telegram_message(message)
        if result and result.get('ok'):
            save_last_sentence(sentence['id'])
            
    elif current_hour == 7:  # 10:00 МСК
        message = f"📝 <b>Проверка диктанта</b>\n\n"
        message += f"🇬🇧 <b>Было:</b> {sentence['en']}\n"
        message += f"🇷🇺 <b>Правильный перевод:</b>\n"
        message += f"<i>{sentence['ru']}</i>\n\n"
        message += f"📊 <b>Разбор:</b>\n"
        message += f"• Тема: {sentence['topic']}\n"
        message += f"• Сложность: {sentence['difficulty']}\n\n"
        message += f"💪 Как твой вариант? Напиши в комментариях!"
        
        send_telegram_message(message)
        
    else:
        print(f"⏰ Не время для отправки. Следующий запуск в 9:00 или 10:00 МСК")
    
    print("🏁 Завершено")

if __name__ == "__main__":
    main()
