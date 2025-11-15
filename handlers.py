import logging
from telegram import Update, InputMediaPhoto
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from config import Config
from gemini_service import GeminiService
from storage import PostStorage, PostData
from keyboards import Keyboards

logger = logging.getLogger(__name__)


class BotHandlers:
    """Обработчики событий бота"""
    
    def __init__(self, gemini_service: GeminiService, storage: PostStorage):
        self.gemini = gemini_service
        self.storage = storage
        self.keyboards = Keyboards()
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Обработка входящего сообщения с новостью (текст или фото с подписью)
        
        Args:
            update: Объект обновления Telegram
            context: Контекст бота
        """
        if not update.message:
            return
        
        # Логируем тип сообщения для отладки
        logger.info(f"Получено сообщение: text={bool(update.message.text)}, photo={bool(update.message.photo)}, video={bool(update.message.video)}, caption={bool(update.message.caption)}, forwarded={bool(update.message.forward_date)}")
        
        # Проверяем флаги ожидания
        if context.user_data.get('waiting_for_manual_edit'):
            await self._handle_manual_edit_input(update, context)
            return
        elif context.user_data.get('waiting_for_ai_edit'):
            await self._handle_ai_edit_input(update, context)
            return
        elif context.user_data.get('waiting_for_image'):
            await self._handle_image_upload(update, context)
            return
        
        # Проверяем, есть ли текст или фото с подписью или видео с подписью
        has_text = bool(update.message.text)
        has_photo_with_caption = bool(update.message.photo and update.message.caption)
        has_video_with_caption = bool(update.message.video and update.message.caption)
        
        if not (has_text or has_photo_with_caption or has_video_with_caption):
            logger.info("Сообщение не подходит под условия обработки")
            return
        
        chat_id = update.message.chat_id
        
        # Получаем текст новости
        if has_text:
            news_text = update.message.text
        else:
            news_text = update.message.caption
        
        logger.info(f"Получена новость от пользователя {chat_id}")
        
        # Отправляем сообщение о начале обработки
        processing_msg = await update.message.reply_text(
            "⏳ Обрабатываю новость..."
        )
        
        try:
            # Проверяем, есть ли фото в сообщении (только если одно фото и нет видео)
            user_image = None
            if update.message.photo and len(update.message.photo) == 1 and not update.message.video:
                # Скачиваем фото пользователя
                photo = update.message.photo[-1]  # Берем самое большое фото
                user_image_file = await photo.get_file()
                user_image = await user_image_file.download_as_bytearray()
                
                # Преобразуем в BytesIO
                from io import BytesIO
                user_image = BytesIO(user_image)
                user_image.seek(0)
            
            # Обрабатываем новость через Gemini
            shortened_text, image = await self.gemini.process_news_full(news_text, processing_msg, user_image)
            
            # Проверяем, что изображение не пустое
            image.seek(0)
            image_data = image.read()
            if len(image_data) == 0:
                raise ValueError("Сгенерированное изображение пустое")
            
            # Возвращаемся к началу BytesIO
            image.seek(0)
            
            # Сохраняем данные поста
            post_data = PostData(
                text=shortened_text,
                image=image,
                chat_id=chat_id,
                original_text=news_text
            )
            self.storage.save(chat_id, post_data)
            
            # Удаляем сообщение о обработке
            try:
                await processing_msg.delete()
            except Exception as e:
                logger.warning(f"Не удалось удалить сообщение об обработке: {e}")
            
            # Отправляем превью поста с кнопками
            await self._send_post_preview(update, shortened_text, image)
            
        except Exception as e:
            logger.error(f"Ошибка при обработке новости: {e}", exc_info=True)
            
            # Пробуем отредактировать сообщение об ошибке
            try:
                await processing_msg.edit_text(
                    f"❌ Ошибка при обработке новости:\n{str(e)}\n\n"
                    f"Попробуйте отправить новость еще раз."
                )
            except Exception:
                # Если не получилось отредактировать, отправляем новое сообщение
                await update.message.reply_text(
                    f"❌ Ошибка при обработке новости:\n{str(e)}\n\n"
                    f"Попробуйте отправить новость еще раз."
                )
    
    async def _send_post_preview(self, update: Update, text: str, image) -> None:
        """
        Отправить превью поста с кнопками
        
        Args:
            update: Объект обновления Telegram
            text: Текст поста
            image: Изображение поста
        """
        # Сбрасываем позицию в начало BytesIO
        image.seek(0)
        
        await update.message.reply_photo(
            photo=image,
            caption=text,
            reply_markup=self.keyboards.get_post_actions_keyboard()
        )
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Обработка нажатий на инлайн-кнопки
        
        Args:
            update: Объект обновления Telegram
            context: Контекст бота
        """
        query = update.callback_query
        await query.answer()
        
        callback_data = query.data
        chat_id = query.message.chat_id
        
        logger.info(f"Получен callback: {callback_data} от пользователя {chat_id}")
        
        # Маршрутизация по типу callback
        handlers_map = {
            "send": self._handle_send,
            "cancel": self._handle_cancel,
            "edit": self._handle_edit,
            "edit_image": self._handle_edit_image,
            "edit_text": self._handle_edit_text,
            "regenerate_image": self._handle_regenerate_image,
            "upload_image": self._handle_upload_image,
            "ai_edit_text": self._handle_ai_edit_text,
            "manual_edit_text": self._handle_manual_edit_text,
            "back_to_preview": self._handle_back_to_preview,
            "back_to_edit": self._handle_back_to_edit,
            "cancel_operation": self._handle_cancel_operation,
        }
        
        handler = handlers_map.get(callback_data)
        if handler:
            await handler(update, context)
        else:
            logger.warning(f"Неизвестный callback: {callback_data}")
    
    async def _handle_send(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Отправить пост в целевую группу"""
        query = update.callback_query
        chat_id = query.message.chat_id
        
        post_data = self.storage.get(chat_id)
        if not post_data:
            await query.edit_message_caption(caption="❌ Данные поста не найдены")
            return
        
        try:
            # Отправляем в целевую группу
            post_data.image.seek(0)
            await context.bot.send_photo(
                chat_id=Config.TARGET_GROUP_ID,
                photo=post_data.image,
                caption=post_data.text
            )
            
            # Уведомляем пользователя
            await query.edit_message_caption(
                caption=f"✅ Пост успешно опубликован!\n\n{post_data.text}"
            )
            
            # Очищаем данные
            self.storage.delete(chat_id)
            
        except Exception as e:
            logger.error(f"Ошибка при отправке поста: {e}")
            await query.edit_message_caption(
                caption=f"❌ Ошибка при отправке: {str(e)}"
            )
    
    async def _handle_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Отменить публикацию"""
        query = update.callback_query
        chat_id = query.message.chat_id
        
        self.storage.delete(chat_id)
        await query.edit_message_caption(caption="❌ Отменено")
    
    async def _handle_edit(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Показать опции редактирования"""
        query = update.callback_query
        await query.edit_message_reply_markup(
            reply_markup=self.keyboards.get_edit_options_keyboard()
        )
    
    async def _handle_edit_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Показать опции редактирования изображения"""
        query = update.callback_query
        await query.edit_message_reply_markup(
            reply_markup=self.keyboards.get_image_edit_keyboard()
        )
    
    async def _handle_edit_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Показать опции редактирования текста"""
        query = update.callback_query
        await query.edit_message_reply_markup(
            reply_markup=self.keyboards.get_text_edit_keyboard()
        )
    
    async def _handle_regenerate_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Перегенерировать изображение"""
        query = update.callback_query
        chat_id = query.message.chat_id
        
        post_data = self.storage.get(chat_id)
        if not post_data:
            await query.answer("❌ Данные не найдены", show_alert=True)
            return
        
        await query.answer("⏳ Генерирую новое изображение...")
        
        try:
            # Отправляем сообщение о начале обработки
            processing_msg = await query.message.reply_text("⏳ Генерирую новое изображение...")
            
            # Генерируем новый промпт и изображение
            image_prompt = await self.gemini.generate_image_prompt(post_data.text)
            
            # Используем executor для синхронного вызова
            import asyncio
            loop = asyncio.get_event_loop()
            new_image = await loop.run_in_executor(
                None,
                lambda: self.gemini._generate_image_sync(image_prompt)
            )
            
            # Проверяем изображение
            new_image.seek(0)
            image_data = new_image.read()
            if len(image_data) == 0:
                raise ValueError("Сгенерированное изображение пустое")
            
            new_image.seek(0)
            
            # Обновляем изображение
            self.storage.update_image(chat_id, new_image)
            
            # Обновляем превью в том же сообщении
            new_image.seek(0)
            media = InputMediaPhoto(media=new_image, caption=post_data.text)
            await query.edit_message_media(
                media=media,
                reply_markup=self.keyboards.get_post_actions_keyboard()
            )
            
            # Удаляем сообщение об обработке
            try:
                await processing_msg.delete()
            except Exception as e:
                logger.warning(f"Не удалось удалить сообщение об обработке: {e}")
            
        except Exception as e:
            logger.error(f"Ошибка при перегенерации изображения: {e}", exc_info=True)
            # Пробуем отредактировать сообщение об ошибке
            try:
                await processing_msg.edit_text(f"❌ Ошибка при генерации изображения: {str(e)}")
            except Exception:
                # Если не получилось отредактировать, отправляем новое сообщение
                await query.answer(f"❌ Ошибка: {str(e)}", show_alert=True)
    
    async def _handle_upload_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Запросить загрузку своего изображения"""
        query = update.callback_query
        context.user_data['waiting_for_image'] = True
        await query.answer()
        await query.message.reply_text(
            "📤 Отправьте изображение, которое хотите использовать",
            reply_markup=self.keyboards.get_cancel_keyboard()
        )
    
    async def _handle_image_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработка загруженного изображения"""
        # Очищаем флаг
        context.user_data.pop('waiting_for_image', None)
        
        # Проверяем, что отправлено фото
        if not update.message.photo:
            await update.message.reply_text("❌ Пожалуйста, отправьте изображение.")
            return
        
        try:
            # Скачиваем фото
            photo = update.message.photo[-1]  # Берем самое большое фото
            user_image_file = await photo.get_file()
            user_image_data = await user_image_file.download_as_bytearray()
            
            # Преобразуем в BytesIO
            from io import BytesIO
            user_image = BytesIO(user_image_data)
            user_image.seek(0)
            
            # Получаем данные поста
            chat_id = update.message.chat_id
            post_data = self.storage.get(chat_id)
            if not post_data:
                await update.message.reply_text("❌ Данные поста не найдены")
                return
            
            # Обновляем изображение
            self.storage.update_image(chat_id, user_image)
            
            # Удаляем сообщение с изображением
            await update.message.delete()
            
            # Отправляем новое превью
            user_image.seek(0)
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=user_image,
                caption=post_data.text,
                reply_markup=self.keyboards.get_post_actions_keyboard()
            )
        except Exception as e:
            logger.error(f"Ошибка при обработке загруженного изображения: {e}")
            await update.message.reply_text(f"❌ Ошибка при обработке изображения: {str(e)}")
    
    async def reset_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Сброс всех данных бота
        
        Args:
            update: Объект обновления Telegram
            context: Контекст бота
        """
        import os
        
        # Очистить файл хранилища
        if os.path.exists(self.storage.storage_file):
            os.remove(self.storage.storage_file)
        
        # Переинициализировать хранилище
        self.storage = PostStorage()
        
        # Очистить пользовательские данные
        context.user_data.clear()
        
        await update.message.reply_text("✅ Все данные сброшены. Вы можете начать заново.")
    
    async def _handle_ai_edit_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """AI редактирование текста"""
        query = update.callback_query
        context.user_data['waiting_for_ai_edit'] = True
        await query.answer()
        await query.message.reply_text(
            "✏️ Напишите, как изменить текст\n"
            "Например: 'Сделай короче' или 'Добавь эмодзи'",
            reply_markup=self.keyboards.get_cancel_keyboard()
        )
    
    async def _handle_ai_edit_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработка ввода для AI редактирования текста"""
        chat_id = update.message.chat_id
        instruction = update.message.text
        
        # Очищаем флаг
        context.user_data.pop('waiting_for_ai_edit', None)
        
        post_data = self.storage.get(chat_id)
        if not post_data:
            await update.message.reply_text("❌ Данные поста не найдены")
            return
        
        try:
            # Отправляем сообщение о начале обработки
            processing_msg = await update.message.reply_text("⏳ Редактирую текст с помощью AI...")
            
            # Редактируем текст через Gemini
            edited_text = await self.gemini.edit_text_with_instruction(post_data.original_text or post_data.text, instruction)
            
            # Обновляем текст
            self.storage.update_text(chat_id, edited_text)
            
            # Удаляем сообщения
            await update.message.delete()
            try:
                await processing_msg.delete()
            except Exception as e:
                logger.warning(f"Не удалось удалить сообщение об обработке: {e}")
            
            # Отправляем новое превью
            post_data.image.seek(0)
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=post_data.image,
                caption=edited_text,
                reply_markup=self.keyboards.get_post_actions_keyboard()
            )
            
        except Exception as e:
            logger.error(f"Ошибка при AI редактировании текста: {e}")
            # Пробуем отредактировать сообщение об ошибке
            try:
                await processing_msg.edit_text(f"❌ Ошибка при редактировании: {str(e)}")
            except Exception:
                # Если не получилось отредактировать, отправляем новое сообщение
                await update.message.reply_text(f"❌ Ошибка при редактировании: {str(e)}")
    
    async def _handle_manual_edit_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Ручное редактирование текста"""
        query = update.callback_query
        context.user_data['waiting_for_manual_edit'] = True
        await query.answer()
        await query.message.reply_text(
            "✏️ Отправьте новый текст для поста",
            reply_markup=self.keyboards.get_cancel_keyboard()
        )
    
    async def _handle_manual_edit_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработка ввода для ручного редактирования текста"""
        chat_id = update.message.chat_id
        new_text = update.message.text
        
        # Очищаем флаг
        context.user_data.pop('waiting_for_manual_edit', None)
        
        post_data = self.storage.get(chat_id)
        if not post_data:
            await update.message.reply_text("❌ Данные поста не найдены")
            return
        
        # Обновляем текст
        self.storage.update_text(chat_id, new_text)
        
        # Удаляем сообщение с новым текстом
        await update.message.delete()
        
        # Отправляем новое превью
        post_data.image.seek(0)
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=post_data.image,
            caption=new_text,
            reply_markup=self.keyboards.get_post_actions_keyboard()
        )
    
    async def _handle_back_to_preview(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Вернуться к превью поста"""
        query = update.callback_query
        await query.edit_message_reply_markup(
            reply_markup=self.keyboards.get_post_actions_keyboard()
        )
    
    async def _handle_back_to_edit(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Вернуться к меню редактирования"""
        query = update.callback_query
        await query.edit_message_reply_markup(
            reply_markup=self.keyboards.get_edit_options_keyboard()
        )
    
    async def _handle_cancel_operation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Отменить текущую операцию редактирования"""
        query = update.callback_query
        
        if not query.message:
            await query.answer("❌ Сообщение не найдено", show_alert=True)
            return
        
        chat_id = query.message.chat_id
        
        logger.info(f"Отмена операции для чата {chat_id}")
        
        # Очищаем флаги ожидания
        context.user_data.pop('waiting_for_manual_edit', None)
        context.user_data.pop('waiting_for_ai_edit', None)
        context.user_data.pop('waiting_for_image', None)
        
        # Получаем данные поста
        post_data = self.storage.get(chat_id)
        logger.info(f"Получены данные поста для чата {chat_id}: {'да' if post_data else 'нет'}")
        
        # Удаляем сообщение с запросом
        try:
            await query.message.edit_text("✅ Операция отменена")
            logger.info(f"Отредактировано сообщение запроса для чата {chat_id}")
        except Exception as e:
            logger.warning(f"Не удалось отредактировать сообщение: {e}")
            # Если не получилось отредактировать, пробуем удалить
            try:
                await query.message.delete()
                logger.info(f"Удалено сообщение запроса для чата {chat_id}")
            except Exception as e2:
                logger.warning(f"Не удалось удалить сообщение: {e2}")
        
        if post_data:
            # Отправляем превью поста заново
            post_data.image.seek(0)
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=post_data.image,
                caption=post_data.text,
                reply_markup=self.keyboards.get_post_actions_keyboard()
            )
            logger.info(f"Отправлено превью поста для чата {chat_id}")
        else:
            await query.answer("✅ Операция отменена")