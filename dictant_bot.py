import json
import random
import os
import requests
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
        # Возвращаем тестовые данные если файл не найден
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
    """Главная функция - тестовый режим"""
    print("🚀 Запуск тестового режима...")
    
    # Загружаем предложения
    sentences = load_sentences()
    print(f"📚 Загружено предложений: {len(sentences)}")
    
    # Выбираем случайное предложение
    sentence = random.choice(sentences)
    print(f"🎯 Выбрано предложение ID: {sentence['id']}")
    
    # ===== ОТПРАВЛЯЕМ АНГЛИЙСКОЕ ПРЕДЛОЖЕНИЕ =====
    message_en = f"📝 <b>ТЕСТОВЫЙ ДИКТАНТ</b>\n\n"
    message_en += f"<b>Тема:</b> {sentence['topic']}\n"
    message_en += f"<b>Сложность:</b> {sentence['difficulty']}\n\n"
    message_en += f"🇬🇧 <b>Переведи на русский:</b>\n"
    message_en += f"<i>{sentence['en']}</i>\n\n"
    message_en += f"⏳ <b>Проверка через минуту</b>"
    
    print(f"\n📝 Отправляем задание...")
    result1 = send_telegram_message(message_en)
    
    if result1 and result1.get('ok'):
        # Сохраняем ID только если первое сообщение ушло
        save_last_sentence(sentence['id'])
        
        # Ждем минуту
        print("⏳ Ждем 60 секунд перед отправкой перевода...")
        import time
        time.sleep(60)
        
        # ===== ОТПРАВЛЯЕМ ПЕРЕВОД =====
        message_ru = f"📝 <b>ПРОВЕРКА ТЕСТОВОГО ДИКТАНТА</b>\n\n"
        message_ru += f"🇬🇧 <b>Было:</b> {sentence['en']}\n"
        message_ru += f"🇷🇺 <b>Правильный перевод:</b>\n"
        message_ru += f"<i>{sentence['ru']}</i>\n\n"
        message_ru += f"📊 <b>Разбор:</b>\n"
        message_ru += f"• Тема: {sentence['topic']}\n"
        message_ru += f"• Сложность: {sentence['difficulty']}\n\n"
        message_ru += f"💪 Как твой вариант? Напиши в комментариях!"
        
        print(f"\n📝 Отправляем перевод...")
        send_telegram_message(message_ru)
    else:
        print("❌ Первое сообщение не отправлено, перевод не будет отправлен")
    
    print("\n🏁 Тест завершен")

if __name__ == "__main__":
    main()
