import json
import random
import os
import requests
from datetime import datetime
import time

# ===== НАСТРОЙКИ =====
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
SENTENCES_FILE = 'sentences.json'

def load_sentences():
    """Загружает предложения из JSON"""
    with open(SENTENCES_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data['sentences']

def get_random_sentence(sentences, last_id=None):
    """Выбирает случайное предложение, не повторяя последнее"""
    if last_id:
        # Исключаем последнее использованное
        available = [s for s in sentences if s['id'] != last_id]
    else:
        available = sentences
    
    if not available:  # Если все предложения использованы
        return random.choice(sentences)
    
    return random.choice(available)

def save_last_sentence(sentence_id):
    """Сохраняет ID последнего предложения"""
    with open('last_sentence.txt', 'w') as f:
        f.write(str(sentence_id))

def load_last_sentence():
    """Загружает ID последнего предложения"""
    try:
        with open('last_sentence.txt', 'r') as f:
            return int(f.read().strip())
    except:
        return None

def send_telegram_message(text):
    """Отправляет сообщение в Telegram"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        'chat_id': CHAT_ID,
        'text': text,
        'parse_mode': 'HTML'
    }
    try:
        response = requests.post(url, data=data)
        return response.json()
    except Exception as e:
        print(f"Ошибка отправки: {e}")
        return None

def main():
    """Главная функция"""
    # Загружаем все предложения
    sentences = load_sentences()
    
    # Загружаем последнее использованное
    last_id = load_last_sentence()
    
    # Выбираем новое предложение
    sentence = get_random_sentence(sentences, last_id)
    
    # Получаем текущее время (в UTC, но мы настроим кроном)
    now = datetime.now()
    hour = now.hour
    
    # Определяем, какое сообщение отправлять
    # Крон настроен на 6 и 7 UTC (9 и 10 МСК)
    
    if hour == 6:  # 9:00 МСК
        # Утром - присылаем английское предложение
        message = f"📝 <b>Ежедневный диктант</b>\n\n"
        message += f"<b>Тема:</b> {sentence['topic']}\n\n"
        message += f"🇬🇧 <b>Переведи на русский:</b>\n"
        message += f"<i>{sentence['en']}</i>\n\n"
        message += f"⏳ <b>Ответ придет через час</b>\n"
        message += f"✍️ Пиши свой вариант в комментарии!"
        
        send_telegram_message(message)
        print(f"Отправлено задание (EN): {sentence['en']}")
        
        # Сохраняем ID для ответа через час
        save_last_sentence(sentence['id'])
    
    elif hour == 7:  # 10:00 МСК
        # Через час - присылаем перевод
        message = f"📝 <b>Проверка диктанта</b>\n\n"
        message += f"🇬🇧 <b>Было:</b> {sentence['en']}\n"
        message += f"🇷🇺 <b>Правильный перевод:</b>\n"
        message += f"<i>{sentence['ru']}</i>\n\n"
        message += f"📊 <b>Разбор:</b>\n"
        message += f"• Тема: {sentence['topic']}\n"
        message += f"• Сложность: {sentence.get('difficulty', 'средняя')}\n\n"
        message += f"💪 Как твой вариант? Похоже? Пиши в комментах!"
        
        send_telegram_message(message)
        print(f"Отправлен ответ (RU): {sentence['ru']}")
    
    else:
        print(f"Не время для отправки. Текущий час UTC: {hour}")

if __name__ == "__main__":
    main()