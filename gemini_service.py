import google.generativeai as genai
from io import BytesIO
from PIL import Image
import logging
import asyncio
import time
from config import Config

logger = logging.getLogger(__name__)


class GeminiService:
    """Сервис для работы с Google Gemini API"""
    
    def __init__(self):
        genai.configure(api_key=Config.GOOGLE_API_KEY)
        self.text_model = genai.GenerativeModel(Config.TEXT_MODEL)
        self.image_model = genai.GenerativeModel(Config.IMAGE_MODEL)
    
    async def shorten_news(self, news_text: str) -> str:
        """
        Сократить новость для поста в соцсетях
        
        Args:
            news_text: Исходный текст новости
            
        Returns:
            Сокращенная версия новости
        """
        prompt = f"Укороти новость: {news_text}. Ответ должен содержать ТОЛЬКО новость!"
        
        for attempt in range(3):
            try:
                response = await self.text_model.generate_content_async(prompt)
                
                if not response or not response.text:
                    raise ValueError("Пустой ответ от модели")
                
                shortened_text = response.text.strip()
                logger.info(f"Новость сокращена: {len(news_text)} -> {len(shortened_text)} символов")
                
                return shortened_text
                
            except Exception as e:
                logger.warning(f"Попытка {attempt + 1} не удалась при сокращении новости: {e}")
                if attempt == 2:
                    logger.error(f"Ошибка при сокращении новости после 3 попыток: {e}")
                    raise
                await asyncio.sleep(2 ** attempt)  # exponential backoff
    
    async def generate_image_prompt(self, news_text: str) -> str:
        """
        Сгенерировать промпт для создания изображения
        
        Args:
            news_text: Текст новости
            
        Returns:
            Промпт для генерации изображения
        """
        prompt = f"Напиши промт для фото к новости, скинь только промт: {news_text}"
        
        for attempt in range(3):
            try:
                response = await self.text_model.generate_content_async(prompt)
                
                if not response or not response.text:
                    raise ValueError("Пустой ответ от модели")
                
                image_prompt = response.text.strip()
                logger.info(f"Сгенерирован промпт для изображения: {image_prompt[:100]}...")
                
                return image_prompt
                
            except Exception as e:
                logger.warning(f"Попытка {attempt + 1} не удалась при генерации промпта: {e}")
                if attempt == 2:
                    logger.error(f"Ошибка при генерации промпта после 3 попыток: {e}")
                    raise
                await asyncio.sleep(2 ** attempt)  # exponential backoff
    

    async def process_news_full(self, news_text: str, message=None, user_image=None) -> tuple[str, BytesIO]:
        """
        Полный цикл обработки новости: сокращение + генерация изображения
        
        Args:
            news_text: Исходный текст новости
            message: Telegram сообщение для обновления статуса (опционально)
            user_image: Пользовательское изображение (опционально)
            
        Returns:
            Кортеж (сокращенный текст, изображение)
        """
        try:
            # Сокращаем текст
            shortened_text = await self.shorten_news(news_text)
            
            # Обновляем сообщение после сокращения текста
            if message:
                await message.edit_text(
                    "Генерирую изображение"
                )
            
            # Проверяем, предоставлено ли пользовательское изображение
            if user_image is not None:
                # Используем предоставленное изображение
                image = user_image
                logger.info("Используем пользовательское изображение")
            else:
                # Генерируем промпт для изображения
                image_prompt = await self.generate_image_prompt(shortened_text)
                
                # Генерируем изображение (используем синхронный вызов в executor)
                import asyncio
                loop = asyncio.get_event_loop()
                image = await loop.run_in_executor(
                    None, 
                    lambda: self._generate_image_sync(image_prompt)
                )
            
            return shortened_text, image
        except Exception as e:
            logger.error(f"Ошибка в process_news_full: {e}")
            raise
    
    def _generate_image_sync(self, prompt: str) -> BytesIO:
        """
        Синхронная генерация изображения (для использования в executor)
        
        Args:
            prompt: Промпт для генерации
            
        Returns:
            BytesIO с изображением
        """
        for attempt in range(3):
            try:
                logger.info(f"Генерация изображения по промпту: {prompt[:100]}...")
                
                response = self.image_model.generate_content(prompt)
                
                if not response:
                    raise ValueError("Пустой ответ от модели")
                
                # Извлекаем изображение
                image_data = None
                
                # Проверяем различные структуры ответа
                if hasattr(response, 'candidates') and len(response.candidates) > 0:
                    candidate = response.candidates[0]
                    if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                        for part in candidate.content.parts:
                            if hasattr(part, 'inline_data') and part.inline_data:
                                image_data = part.inline_data.data
                                break
                
                if not image_data and hasattr(response, 'parts'):
                    for part in response.parts:
                        if hasattr(part, 'inline_data') and part.inline_data:
                            image_data = part.inline_data.data
                            break
                
                # Если изображение не получено, создаем заглушку
                if not image_data:
                    logger.warning("Не удалось извлечь изображение из ответа API, создаем заглушку")
                    return self._create_placeholder_image(prompt)
                
                # Декодируем base64 если нужно
                if isinstance(image_data, str):
                    import base64
                    image_data = base64.b64decode(image_data)
                
                image_bytes = BytesIO(image_data)
                image_bytes.seek(0)
                
                size = len(image_data)
                if size == 0:
                    logger.warning("Изображение пустое, создаем заглушку")
                    return self._create_placeholder_image(prompt)
                
                logger.info(f"Изображение успешно сгенерировано (размер: {size} байт)")
                return image_bytes
                
            except Exception as e:
                logger.warning(f"Попытка {attempt + 1} не удалась при генерации изображения: {e}")
                if attempt == 2:
                    logger.error(f"Ошибка при генерации изображения после 3 попыток: {e}")
                    logger.info("Создаем изображение-заглушку")
                    return self._create_placeholder_image(prompt)
                time.sleep(2 ** attempt)  # exponential backoff
    
    async def edit_text_with_instruction(self, current_text: str, instruction: str) -> str:
        """
        Редактировать текст по инструкции
        
        Args:
            current_text: Текущий текст поста
            instruction: Инструкция редактирования
            
        Returns:
            Отредактированный текст
        """
        prompt = f"Изменить текст согласно инструкции: '{instruction}'. Текущий текст: '{current_text}'. Верни только измененный текст, без лишних объяснений."
        
        for attempt in range(3):
            try:
                response = await self.text_model.generate_content_async(prompt)
                
                if not response or not response.text:
                    raise ValueError("Пустой ответ от модели")
                
                edited_text = response.text.strip()
                logger.info(f"Текст отредактирован: '{current_text}' -> '{edited_text}' по инструкции '{instruction}'")
                
                return edited_text
                
            except Exception as e:
                logger.warning(f"Попытка {attempt + 1} не удалась при редактировании текста: {e}")
                if attempt == 2:
                    logger.error(f"Ошибка при редактировании текста после 3 попыток: {e}")
                    raise
                await asyncio.sleep(2 ** attempt)  # exponential backoff
    
    def _create_placeholder_image(self, text: str) -> BytesIO:
        """
        Создать изображение-заглушку
        
        Args:
            text: Текст для отображения
            
        Returns:
            BytesIO с изображением
        """
        from PIL import Image, ImageDraw, ImageFont
        
        # Создаем красивое изображение
        img = Image.new('RGB', (1200, 630), color='#1a1a2e')
        draw = ImageDraw.Draw(img)
        
        # Заголовок
        title = "🖼️ Новость"
        try:
            # Пытаемся использовать системный шрифт
            font_title = ImageFont.truetype("arial.ttf", 60)
            font_text = ImageFont.truetype("arial.ttf", 30)
        except:
            font_title = ImageFont.load_default()
            font_text = ImageFont.load_default()
        
        # Рисуем заголовок
        bbox = draw.textbbox((0, 0), title, font=font_title)
        title_width = bbox[2] - bbox[0]
        draw.text(((1200 - title_width) // 2, 200), title, fill='#ffffff', font=font_title)
        
        # Рисуем подзаголовок
        subtitle = "Изображение генерируется..."
        bbox = draw.textbbox((0, 0), subtitle, font=font_text)
        subtitle_width = bbox[2] - bbox[0]
        draw.text(((1200 - subtitle_width) // 2, 300), subtitle, fill='#888888', font=font_text)
        
        # Сохраняем в BytesIO
        image_bytes = BytesIO()
        img.save(image_bytes, format='PNG')
        image_bytes.seek(0)
        
        return image_bytes