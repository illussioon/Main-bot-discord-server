# Discord Economy & Management Bot

Многофункциональный Discord бот с системой экономики, личных комнат, ролей и браков.

## Основные функции

### Экономика
- Двойная валюта: монеты (💰) и звезды (⭐)
- Система переводов между пользователями с комиссией
- Конвертация валют

### Личные роли
- Создание собственных ролей
- Управление цветом и названием роли
- Возможность выдавать роли другим пользователям
- Полное логирование всех действий с ролями

### Приватные комнаты
- Создание личных голосовых комнат
- Система совладельцев
- Управление доступом
- Настройка названия и цвета роли комнаты
- Логирование всех действий

### Система браков
- Создание пар между пользователями
- Автоматическое создание любовных комнат
- Специальная роль для женатых/замужних
- Полное логирование всех действий

### Профиль пользователя ⚠️
- Отображение статистики пользователя
- Визуальное представление в виде изображения
- Показ баланса и активности
> ⚠️ Команда /profile находится в разработке и требует доработки

## Команды пользователей

### Экономика
- `/give` - Передать валюту другому пользователю

### Роли
- `/role create` - Создать личную роль
- `/role manage` - Управление существующими ролями

### Комнаты
- `/room` - Управление приватными комнатами
- `/addroom` - Создание приватной комнаты [ADMIN]

### Отношения
- `/marry` - Сделать предложение другому игроку
- `/divorce` - Развестись с игроком

### Прочее
- `/profile` - Показать профиль пользователя (в разработке)

## Установка

1. Клонируйте репозиторий
2. Установите зависимости:

bash
pip install discord.py Pillow aiohttp


3. Настройте `config.py`:
   - Укажите ID вашего сервера
   - Настройте ID категорий и каналов
   - Укажите пути к файлам профиля
4. Создайте папку `assets` и добавьте:
   - Шаблон профиля (`profile.png`)
   - Шрифт для профиля (`font.ttf`)
5. Запустите бота:


bash
python bot.py



## Конфигурация

Все настройки бота находятся в файле `config.py`:
- ID каналов для логирования
- Цены на различные действия
- Настройки валют
- Пути к ресурсам

## Требования
- Python 3.8+
- discord.py
- Pillow
- aiohttp
- SQLite3

## Лицензия
MIT License

## Автор
[kompromizz]

