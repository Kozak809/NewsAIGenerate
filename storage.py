from dataclasses import dataclass
from io import BytesIO
from typing import Optional
import logging
import json
import os
import base64
import tempfile

logger = logging.getLogger(__name__)


@dataclass
class PostData:
    """Данные поста для публикации"""
    text: str
    image: BytesIO
    chat_id: int
    original_text: Optional[str] = None
    message_id: Optional[int] = None


class PostStorage:
    """Хранилище данных постов для обработки"""
    
    def __init__(self, storage_file: str = "post_storage.json"):
        self.storage_file = storage_file
        self._posts: dict[int, PostData] = {}
        self._load_from_disk()
        logger.info(f"Storage инициализирован, постов: {len(self._posts)}")
    
    def _load_from_disk(self) -> None:
        """Загрузить данные с диска"""
        if os.path.exists(self.storage_file):
            logger.info(f"Найден файл storage: {self.storage_file}")
            try:
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                logger.info(f"Загружен JSON с {len(data)} записями")
                
                for chat_id_str, post_dict in data.items():
                    chat_id = int(chat_id_str)
                    # Восстанавливаем BytesIO из base64
                    image_data = base64.b64decode(post_dict['image_base64'])
                    image = BytesIO(image_data)
                    image.seek(0)
                    
                    post_data = PostData(
                        text=post_dict['text'],
                        image=image,
                        chat_id=chat_id,
                        original_text=post_dict.get('original_text'),
                        message_id=post_dict.get('message_id')
                    )
                    self._posts[chat_id] = post_data
                
                logger.info(f"Загружены данные для {len(self._posts)} постов")
            except Exception as e:
                logger.error(f"Ошибка загрузки данных: {e}")
                # Удаляем поврежденный файл
                try:
                    os.remove(self.storage_file)
                    logger.info("Поврежденный файл storage удален")
                except:
                    pass
        else:
            logger.info(f"Файл storage не найден: {self.storage_file}")
    
    def _save_to_disk(self) -> None:
        """Сохранить данные на диск"""
        try:
            data = {}
            for chat_id, post_data in self._posts.items():
                # Сохраняем изображение как base64
                post_data.image.seek(0)
                image_data = post_data.image.read()
                image_base64 = base64.b64encode(image_data).decode('utf-8')
                
                data[str(chat_id)] = {
                    'text': post_data.text,
                    'original_text': post_data.original_text,
                    'image_base64': image_base64,
                    'chat_id': post_data.chat_id,
                    'message_id': post_data.message_id
                }
            
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"Сохранены данные для {len(self._posts)} постов")
        except Exception as e:
            logger.error(f"Ошибка сохранения данных: {e}")
    
    def save(self, chat_id: int, post_data: PostData) -> None:
        """
        Сохранить данные поста
        
        Args:
            chat_id: ID чата
            post_data: Данные поста
        """
        self._posts[chat_id] = post_data
        self._save_to_disk()
        logger.info(f"Сохранены данные поста для чата {chat_id}")
    
    def get(self, chat_id: int) -> Optional[PostData]:
        """
        Получить данные поста
        
        Args:
            chat_id: ID чата
            
        Returns:
            Данные поста или None
        """
        return self._posts.get(chat_id)
    
    def delete(self, chat_id: int) -> None:
        """
        Удалить данные поста
        
        Args:
            chat_id: ID чата
        """
        if chat_id in self._posts:
            del self._posts[chat_id]
            self._save_to_disk()
            logger.info(f"Удалены данные поста для чата {chat_id}")
    
    def update_text(self, chat_id: int, new_text: str) -> bool:
        """
        Обновить текст поста
        
        Args:
            chat_id: ID чата
            new_text: Новый текст
            
        Returns:
            True если обновлено, False если пост не найден
        """
        post = self.get(chat_id)
        if post:
            post.text = new_text
            self._save_to_disk()
            logger.info(f"Обновлен текст поста для чата {chat_id}")
            return True
        return False
    
    def update_image(self, chat_id: int, new_image: BytesIO) -> bool:
        """
        Обновить изображение поста
        
        Args:
            chat_id: ID чата
            new_image: Новое изображение
            
        Returns:
            True если обновлено, False если пост не найден
        """
        post = self.get(chat_id)
        if post:
            post.image = new_image
            self._save_to_disk()
            logger.info(f"Обновлено изображение поста для чата {chat_id}")
            return True
        return False
    
    def clear(self) -> None:
        """Очистить все данные"""
        self._posts.clear()
        if os.path.exists(self.storage_file):
            os.remove(self.storage_file)
        logger.info("Все данные постов очищены")