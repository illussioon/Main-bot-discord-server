import sqlite3
from typing import Dict, Any
from config import CURRENCY_COINS, CURRENCY_DIAMONDS
import discord

class Database:
    def __init__(self, db_name: str = "bot.db"):
        self.db_name = db_name
        self.init_database()

    def init_database(self):
        """Инициализация базы данных и создание необходимых таблиц"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            
            # Создаем таблицу для хранения балансов
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_balance (
                    user_id INTEGER PRIMARY KEY,
                    coins INTEGER DEFAULT 0,
                    diamonds INTEGER DEFAULT 0
                )
            """)
            
            # Создаем таблицу для личных ролей
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS roles (
                    role_id INTEGER PRIMARY KEY,
                    guild_id INTEGER NOT NULL,
                    owner_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Создаем таблицу для связи пользователей и ролей
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_roles (
                    user_id INTEGER NOT NULL,
                    role_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    is_enabled BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, role_id, guild_id)
                )
            """)
            
            # Таблица для приватных комнат
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS private_rooms (
                    room_id INTEGER PRIMARY KEY,    -- ID текстового канала
                    voice_id INTEGER NOT NULL,      -- ID голосового канала
                    role_id INTEGER NOT NULL,       -- ID роли доступа
                    guild_id INTEGER NOT NULL,
                    owner_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица для связи пользователей и комнат
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS room_members (
                    user_id INTEGER NOT NULL,
                    room_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    is_owner BOOLEAN DEFAULT 0,
                    is_coowner BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, room_id, guild_id)
                )
            """)
            
            # Таблица для отслеживания времени в комнате
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS room_time (
                    user_id INTEGER NOT NULL,
                    room_id INTEGER NOT NULL,
                    total_time INTEGER DEFAULT 0,  -- Общее время в секундах
                    last_join TIMESTAMP,          -- Время последнего входа
                    PRIMARY KEY (user_id, room_id)
                )
            """)
            
            # Таблица для браков
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS marriages (
                    user1_id INTEGER NOT NULL,
                    user2_id INTEGER NOT NULL,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user1_id, user2_id)
                )
            """)
            
            # Таблица для отслеживания времени в голосовых каналах
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS voice_activity (
                    user_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    total_time INTEGER DEFAULT 0,
                    last_join TIMESTAMP,
                    PRIMARY KEY (user_id, guild_id)
                )
            """)
            
            # Таблица для отслеживания сообщений
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS message_activity (
                    user_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    message_count INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, guild_id)
                )
            """)
            
            conn.commit()

    def get_balance(self, user_id: int) -> Dict[str, int]:
        """Получение баланса пользователя"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT coins, diamonds FROM user_balance WHERE user_id = ?",
                (user_id,)
            )
            result = cursor.fetchone()
            
            if result is None:
                # Если пользователя нет в БД, создаем запись
                cursor.execute(
                    "INSERT INTO user_balance (user_id, coins, diamonds) VALUES (?, 0, 0)",
                    (user_id,)
                )
                conn.commit()
                return {"coins": 0, "diamonds": 0}
            
            return {"coins": result[0], "diamonds": result[1]}

    def update_balance(self, user_id: int, coins: int = None, diamonds: int = None):
        """Обновление баланса пользователя"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            
            if coins is not None:
                cursor.execute(
                    "UPDATE user_balance SET coins = ? WHERE user_id = ?",
                    (coins, user_id)
                )
            
            if diamonds is not None:
                cursor.execute(
                    "UPDATE user_balance SET diamonds = ? WHERE user_id = ?",
                    (diamonds, user_id)
                )
            
            conn.commit() 

    def add_currency(self, user_id: int, currency_type: str, amount: int):
        """Добавление валюты пользователю"""
        current_balance = self.get_balance(user_id)
        
        if currency_type.lower() == "coins":
            new_amount = current_balance["coins"] + amount
            self.update_balance(user_id, coins=new_amount)
        elif currency_type.lower() == "diamonds":
            new_amount = current_balance["diamonds"] + amount
            self.update_balance(user_id, diamonds=new_amount)
            
        return self.get_balance(user_id) 

    def add_role(self, role_id: int, guild_id: int, owner_id: int):
        """Добавление новой роли"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO roles (role_id, guild_id, owner_id) VALUES (?, ?, ?)",
                (role_id, guild_id, owner_id)
            )
            # Автоматически добавляем роль владельцу
            cursor.execute(
                "INSERT OR REPLACE INTO user_roles (user_id, role_id, guild_id) VALUES (?, ?, ?)",
                (owner_id, role_id, guild_id)
            )
            conn.commit()

    def add_user_role(self, user_id: int, role_id: int, guild_id: int):
        """Добавление роли пользователю"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO user_roles (user_id, role_id, guild_id) VALUES (?, ?, ?)",
                (user_id, role_id, guild_id)
            )
            conn.commit()

    def toggle_role(self, user_id: int, role_id: int, guild_id: int, enabled: bool):
        """Включение/выключение роли"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE user_roles SET is_enabled = ? WHERE user_id = ? AND role_id = ? AND guild_id = ?",
                (enabled, user_id, role_id, guild_id)
            )
            conn.commit()

    def get_user_roles(self, user_id: int, guild_id: int) -> list:
        """Получение списка ролей пользователя"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT r.role_id, ur.is_enabled, 
                       CASE WHEN r.owner_id = ? THEN 1 ELSE 0 END as is_owner
                FROM roles r
                JOIN user_roles ur ON r.role_id = ur.role_id
                WHERE ur.user_id = ? AND r.guild_id = ?
            """, (user_id, user_id, guild_id))
            return cursor.fetchall()

    def delete_role(self, role_id: int, guild_id: int):
        """Удаление роли"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM roles WHERE role_id = ? AND guild_id = ?", (role_id, guild_id))
            cursor.execute("DELETE FROM user_roles WHERE role_id = ? AND guild_id = ?", (role_id, guild_id))
            conn.commit()

    def is_role_owner(self, user_id: int, role_id: int, guild_id: int) -> bool:
        """Проверка является ли пользователь владельцем роли"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM roles WHERE role_id = ? AND guild_id = ? AND owner_id = ?",
                (role_id, guild_id, user_id)
            )
            return cursor.fetchone() is not None 

    def add_private_room(self, room_id: int, voice_id: int, role_id: int, 
                       guild_id: int, owner_id: int, name: str):
        """Добавление новой приватной комнаты"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO private_rooms 
                   (room_id, voice_id, role_id, guild_id, owner_id, name) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (room_id, voice_id, role_id, guild_id, owner_id, name)
            )
            # Добавляем владельца в members
            cursor.execute(
                """INSERT INTO room_members 
                   (user_id, room_id, guild_id, is_owner) 
                   VALUES (?, ?, ?, 1)""",
                (owner_id, room_id, guild_id)
            )
            conn.commit()

    def get_user_rooms(self, user_id: int, guild_id: int) -> list:
        """Получение списка комнат пользователя"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    pr.room_id,
                    pr.voice_id,
                    pr.role_id,
                    pr.name,
                    rm.is_owner,
                    rm.is_coowner
                FROM private_rooms pr
                JOIN room_members rm ON pr.room_id = rm.room_id
                WHERE rm.user_id = ? AND pr.guild_id = ?
            """, (user_id, guild_id))
            return cursor.fetchall()

    def add_room_member(self, user_id: int, room_id: int, guild_id: int, 
                       is_coowner: bool = False):
        """Добавление пользователя в комнату"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT OR REPLACE INTO room_members 
                   (user_id, room_id, guild_id, is_coowner) 
                   VALUES (?, ?, ?, ?)""",
                (user_id, room_id, guild_id, is_coowner)
            )
            conn.commit()

    def remove_room_member(self, user_id: int, room_id: int, guild_id: int):
        """Удаление пользователя из комнаты"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM room_members WHERE user_id = ? AND room_id = ? AND guild_id = ?",
                (user_id, room_id, guild_id)
            )
            conn.commit()

    def delete_room(self, room_id: int, guild_id: int):
        """Удаление комнаты"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM private_rooms WHERE room_id = ? AND guild_id = ?",
                (room_id, guild_id)
            )
            cursor.execute(
                "DELETE FROM room_members WHERE room_id = ? AND guild_id = ?",
                (room_id, guild_id)
            )
            conn.commit() 

    def get_room_data(self, room_id: int) -> dict:
        """Получение информации о комнате"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT room_id, voice_id, role_id, guild_id, owner_id, name
                FROM private_rooms 
                WHERE room_id = ?
            """, (room_id,))
            
            result = cursor.fetchone()
            if result:
                return {
                    "room_id": result[0],
                    "voice_id": result[1],
                    "role_id": result[2],
                    "guild_id": result[3],
                    "owner_id": result[4],
                    "name": result[5]
                }
            return None 

    def update_room_time(self, user_id: int, room_id: int, is_join: bool):
        """Обновление времени в комнате"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            if is_join:
                # Пользователь зашел в комнату
                cursor.execute(
                    """INSERT OR REPLACE INTO room_time 
                       (user_id, room_id, last_join) 
                       VALUES (?, ?, CURRENT_TIMESTAMP)""",
                    (user_id, room_id)
                )
            else:
                # Пользователь вышел из комнаты
                cursor.execute("""
                    UPDATE room_time 
                    SET total_time = total_time + 
                        (strftime('%s', 'now') - strftime('%s', last_join)),
                        last_join = NULL
                    WHERE user_id = ? AND room_id = ? AND last_join IS NOT NULL
                """, (user_id, room_id))
            conn.commit()

    def get_room_members(self, room_id: int) -> list:
        """Получение списка пользователей комнаты с их временем"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    rm.user_id,
                    rm.is_owner,
                    rm.is_coowner,
                    COALESCE(rt.total_time, 0) as total_time,
                    rt.last_join
                FROM room_members rm
                LEFT JOIN room_time rt ON rm.user_id = rt.user_id AND rm.room_id = rt.room_id
                WHERE rm.room_id = ?
                ORDER BY rm.is_owner DESC, rm.is_coowner DESC
            """, (room_id,))
            return cursor.fetchall() 

    def get_member_data(self, user_id: int, room_id: int) -> dict:
        """Получение данных участника комнаты"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT is_owner, is_coowner
                FROM room_members
                WHERE user_id = ? AND room_id = ?
            """, (user_id, room_id))
            result = cursor.fetchone()
            if result:
                return {
                    "is_owner": result[0],
                    "is_coowner": result[1]
                }
            return None

    def get_room_by_voice(self, voice_id: int) -> dict:
        """Получение данных комнаты по ID голосового канала"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT room_id, voice_id, role_id, guild_id, owner_id, name
                FROM private_rooms 
                WHERE voice_id = ?
            """, (voice_id,))
            result = cursor.fetchone()
            if result:
                return {
                    "room_id": result[0],
                    "voice_id": result[1],
                    "role_id": result[2],
                    "guild_id": result[3],
                    "owner_id": result[4],
                    "name": result[5]
                }
            return None 

    def update_room_name(self, room_id: int, new_name: str):
        """Обновление названия комнаты"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE private_rooms SET name = ? WHERE room_id = ?",
                (new_name, room_id)
            )
            conn.commit() 

    def update_room_member(self, user_id: int, room_id: int, guild_id: int, is_coowner: bool):
        """Обновление статуса совладельца"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE room_members 
                   SET is_coowner = ?
                   WHERE user_id = ? AND room_id = ? AND guild_id = ?""",
                (is_coowner, user_id, room_id, guild_id)
            )
            conn.commit() 

    def add_marriage(self, user1_id: int, user2_id: int):
        """Регистрация брака между пользователями"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            # Сортируем ID, чтобы избежать дубликатов
            min_id = min(user1_id, user2_id)
            max_id = max(user1_id, user2_id)
            cursor.execute(
                "INSERT OR REPLACE INTO marriages (user1_id, user2_id) VALUES (?, ?)",
                (min_id, max_id)
            )
            conn.commit()

    def remove_marriage(self, user1_id: int, user2_id: int):
        """Удаление брака"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            min_id = min(user1_id, user2_id)
            max_id = max(user1_id, user2_id)
            cursor.execute(
                "DELETE FROM marriages WHERE user1_id = ? AND user2_id = ?",
                (min_id, max_id)
            )
            conn.commit()

    def get_marriage(self, user_id: int) -> tuple:
        """Получение информации о браке пользователя"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user1_id, user2_id, started_at 
                FROM marriages 
                WHERE user1_id = ? OR user2_id = ?
            """, (user_id, user_id))
            return cursor.fetchone() 

    def update_voice_activity(self, user_id: int, guild_id: int, is_join: bool):
        """Обновление времени в голосовых каналах"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            if is_join:
                cursor.execute("""
                    INSERT OR REPLACE INTO voice_activity 
                    (user_id, guild_id, total_time, last_join)
                    VALUES (
                        ?, ?, 
                        COALESCE((SELECT total_time FROM voice_activity 
                                WHERE user_id = ? AND guild_id = ?), 0),
                        CURRENT_TIMESTAMP
                    )
                """, (user_id, guild_id, user_id, guild_id))
            else:
                cursor.execute("""
                    UPDATE voice_activity 
                    SET total_time = total_time + 
                        (strftime('%s', 'now') - strftime('%s', last_join)),
                        last_join = NULL
                    WHERE user_id = ? AND guild_id = ? AND last_join IS NOT NULL
                """, (user_id, guild_id))
            conn.commit()

    def increment_messages(self, user_id: int, guild_id: int):
        """Увеличение счетчика сообщений"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO message_activity (user_id, guild_id, message_count)
                VALUES (?, ?, 1)
                ON CONFLICT(user_id, guild_id) DO UPDATE SET
                message_count = message_count + 1
            """, (user_id, guild_id))
            conn.commit()

    def get_user_stats(self, user_id: int, guild_id: int) -> dict:
        """Получение статистики пользователя"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            
            # Получаем время в войсе
            cursor.execute("""
                SELECT 
                    COALESCE(total_time, 0) as total_time,
                    last_join
                FROM voice_activity 
                WHERE user_id = ? AND guild_id = ?
            """, (user_id, guild_id))
            voice_data = cursor.fetchone() or (0, None)
            
            # Если пользователь сейчас в войсе, добавляем текущее время
            current_time = voice_data[0]
            if voice_data[1]:
                current_time += int(
                    discord.utils.utcnow().timestamp() - 
                    discord.utils.parse_time(voice_data[1]).timestamp()
                )
            
            # Получаем количество сообщений
            cursor.execute("""
                SELECT COALESCE(message_count, 0)
                FROM message_activity 
                WHERE user_id = ? AND guild_id = ?
            """, (user_id, guild_id))
            messages = cursor.fetchone()
            
            return {
                "voice_time": current_time,
                "messages": messages[0] if messages else 0
            } 