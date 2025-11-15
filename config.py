import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Конфигурация бота"""
    
    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    TARGET_GROUP_ID = os.getenv('TARGET_GROUP_ID', '-123')
    
    # Google Gemini API
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
    
    # Модели Gemini
    TEXT_MODEL = 'gemini-2.5-pro-preview-03-25'
    IMAGE_MODEL = 'gemini-2.5-flash-image-preview'
    
    @classmethod
    def validate(cls):
        """Проверка наличия обязательных параметров"""
        required = {
            'TELEGRAM_BOT_TOKEN': cls.TELEGRAM_BOT_TOKEN,
            'GOOGLE_API_KEY': cls.GOOGLE_API_KEY,
            'TARGET_GROUP_ID': cls.TARGET_GROUP_ID
        }
        
        missing = [key for key, value in required.items() if not value]
        
        if missing:
            raise ValueError(
                f"Отсутствуют обязательные переменные окружения: {', '.join(missing)}"
            )