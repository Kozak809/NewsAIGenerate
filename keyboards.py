from telegram import InlineKeyboardButton, InlineKeyboardMarkup


class Keyboards:
    """Клавиатуры для бота"""
    
    @staticmethod
    def get_post_actions_keyboard() -> InlineKeyboardMarkup:
        """
        Клавиатура с действиями для поста
        
        Returns:
            Клавиатура с кнопками: Отправить, Отменить, Изменить
        """
        keyboard = [
            [InlineKeyboardButton("Отправить", callback_data="send")],
            [InlineKeyboardButton("Отменить", callback_data="cancel")],
            [InlineKeyboardButton("Изменить", callback_data="edit")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_edit_options_keyboard() -> InlineKeyboardMarkup:
        """
        Клавиатура с опциями редактирования
        
        Returns:
            Клавиатура с кнопками редактирования
        """
        keyboard = [
            [InlineKeyboardButton("Изменить изображение", callback_data="edit_image")],
            [InlineKeyboardButton("Изменить текст", callback_data="edit_text")],
            [InlineKeyboardButton("« Назад", callback_data="back_to_preview")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_image_edit_keyboard() -> InlineKeyboardMarkup:
        """
        Клавиатура для редактирования изображения
        
        Returns:
            Клавиатура с опциями редактирования изображения
        """
        keyboard = [
            [InlineKeyboardButton("Перегенерировать", callback_data="regenerate_image")],
            [InlineKeyboardButton("Загрузить своё", callback_data="upload_image")],
            [InlineKeyboardButton("« Назад", callback_data="back_to_edit")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_text_edit_keyboard() -> InlineKeyboardMarkup:
        """
        Клавиатура для редактирования текста
        
        Returns:
            Клавиатура с опциями редактирования текста
        """
        keyboard = [
            [InlineKeyboardButton("AI редактирование", callback_data="ai_edit_text")],
            [InlineKeyboardButton("Вручную", callback_data="manual_edit_text")],
            [InlineKeyboardButton("« Назад", callback_data="back_to_edit")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_cancel_keyboard() -> InlineKeyboardMarkup:
        """
        Клавиатура с кнопкой отмены
        
        Returns:
            Клавиатура с кнопкой отмены
        """
        keyboard = [
            [InlineKeyboardButton("Отменить", callback_data="cancel_operation")]
        ]
        return InlineKeyboardMarkup(keyboard)