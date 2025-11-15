import logging
from telegram.ext import Application, MessageHandler, CallbackQueryHandler, CommandHandler, filters

from config import Config
from gemini_service import GeminiService
from storage import PostStorage
from handlers import BotHandlers

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Главная функция запуска бота"""
    
    # Проверяем конфигурацию
    try:
        Config.validate()
    except ValueError as e:
        logger.error(f"Ошибка конфигурации: {e}")
        return
    
    logger.info("Запуск бота...")
    
    # Инициализируем сервисы
    gemini_service = GeminiService()
    storage = PostStorage()
    handlers = BotHandlers(gemini_service, storage)
    
    # Создаем приложение бота
    application = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()
    
    # Регистрируем обработчики
    # Обработка текстовых сообщений и сообщений с фото/видео (новостей)
    application.add_handler(
        MessageHandler((filters.TEXT | filters.PHOTO | filters.VIDEO) & ~filters.COMMAND, handlers.handle_message)
    )
    
    # Обработка нажатий на кнопки
    application.add_handler(CallbackQueryHandler(handlers.handle_callback))
    
    # Обработка команд
    application.add_handler(CommandHandler("reset", handlers.reset_command))
    
    # Запускаем бота
    logger.info("Бот запущен и готов к работе")
    application.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == '__main__':
    main()