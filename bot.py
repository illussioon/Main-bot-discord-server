import discord
from discord import app_commands
from discord.ext import commands
import asyncio
from database import Database
from config import (
    CURRENCY_COINS, 
    CURRENCY_DIAMONDS,
    GUILD_ID,
    EMOJI_COINS,
    EMOJI_DIAMONDS,
    CONVERSION_RATE,
    DUEL_TIMEOUT,
    TRANSFER_FEE,
    BUTTON_TIMEOUT,
    ROLE_COLOR_PRICE,
    ROLE_NAME_PRICE,
    ROLE_CREATE_PRICE,
    PRIVATE_CATEGORY_ID,
    ROOM_RENAME_PRICE,
    ROOM_COLOR_PRICE,
    ROOM_LOG_CHANNEL_ID,
    TRANSFER_LOG_CHANNEL_ID,
    MARRY_PRICE,
    LOVE_CATEGORY_ID,
    LOVE_VOICE_TRANSFER_ID,
    LOVE_ROLE_ID,
    LOVE_LOG_CHANNEL_ID,
    PROFILE_TEMPLATE_PATH,
    PROFILE_FONT_PATH,
    BOT_TOKEN,  # Добавляем импорт токена
)
import random
from typing import Literal
from PIL import Image, ImageDraw, ImageFont
import io
import aiohttp

class Bot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=discord.Intents.all(),
            application_id="1323393096712589342"
        )
        self.tree_commands = {}
        self.db = Database()
        self.GUILD = discord.Object(id=GUILD_ID)
        self.love_channels = {}

    async def setup_hook(self):
        try:
            print("Начинаем регистрацию команд...")
            
            # Регистрируем обычные команды
            self.remove_command('help')  # Удаляем стандартную команду help
            
            # Синхронизируем слеш-команды
            await self.tree.sync()
            await self.tree.sync(guild=self.GUILD)
            
            print("Команды успешно зарегистрированы!")
            
            # Проверяем команды
            global_commands = await self.tree.fetch_commands()
            guild_commands = await self.tree.fetch_commands(guild=self.GUILD)
            
            print("\nГлобальные команды:")
            for cmd in global_commands:
                print(f"/{cmd.name} - {cmd.description}")
                
            print("\nКоманды сервера:")
            for cmd in guild_commands:
                print(f"/{cmd.name} - {cmd.description}")
                
        except Exception as e:
            print(f"Ошибка при регистрации команд: {e}")

    async def on_ready(self):
        print(f"Бот {self.user} готов к работе!")
        print("\nСписок всех серверов:")
        for guild in self.guilds:
            print(f"- {guild.name} (ID: {guild.id})")
        
        print("\nСписок всех команд:")
        commands = await self.tree.fetch_commands()
        for cmd in commands:
            print(f"/{cmd.name} - {cmd.description}")

    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        try:
            # Обновляем статистику только если пользователь не бот
            if not member.bot:
                # Если пользователь присоединился к каналу
                if after.channel and not before.channel:
                    self.db.update_voice_activity(member.id, member.guild.id, True)
                # Если пользователь покинул канал
                elif before.channel and not after.channel:
                    self.db.update_voice_activity(member.id, member.guild.id, False)
                # Если пользователь перешел между каналами, ничего не делаем
            
            # Если пользователь зашел в войс переводник
            if after.channel and after.channel.id == LOVE_VOICE_TRANSFER_ID:
                # Проверяем, есть ли у пользователя брак
                marriage = self.db.get_marriage(member.id)
                if marriage:
                    # Создаем канал
                    category = member.guild.get_channel(LOVE_CATEGORY_ID)
                    if category:
                        partner_id = marriage[1] if marriage[0] == member.id else marriage[0]
                        partner = member.guild.get_member(partner_id)
                        if partner:
                            # Используем Discord теги (username) вместо display_name
                            channel_name = f"{member.name} ❤️ {partner.name}"
                            voice_channel = await member.guild.create_voice_channel(
                                name=channel_name,
                                category=category,
                                user_limit=2
                            )
                            await member.move_to(voice_channel)
                            
                            # Запоминаем канал для последующего удаления
                            self.love_channels[voice_channel.id] = {
                                "creator": member.id,
                                "partner": partner_id
                            }

                            # Логируем создание канала
                            await send_log(
                                self,
                                "Создана любовная комната",
                                f"**Создатель:** {member.mention} (`{member.id}`)\n"
                                f"**Партнер:** {partner.mention} (`{partner_id}`)\n"
                                f"**Канал:** {voice_channel.mention}",
                                log_type="love",
                                color=0xFF69B4
                            )

            # Если пользователь вышел из канала
            if before.channel and before.channel.id in self.love_channels:
                # Если в канале никого не осталось
                if len(before.channel.members) == 0:
                    channel_info = self.love_channels[before.channel.id]
                    creator = member.guild.get_member(channel_info["creator"])
                    partner = member.guild.get_member(channel_info["partner"])
                    
                    # Логируем удаление канала
                    creator_mention = creator.mention if creator else f"<@{channel_info.get('creator')}>"
                    partner_mention = partner.mention if partner else f"<@{channel_info.get('partner')}>"

                    await send_log(
                        self,
                        "Удалена любовная комната",
                        f"**Владельцы:** {creator_mention} и {partner_mention}\n"
                        f"**Канал:** {before.channel.name}",
                        log_type="love",
                        color=0xFF0000
                    )
                    
                    await before.channel.delete()
                    del self.love_channels[before.channel.id]

        except Exception as e:
            print(f"[ERROR] Error in voice state update: {str(e)}")

    async def on_message(self, message: discord.Message):
        # Увеличиваем счетчик сообщений, если сообщение не от бота
        if not message.author.bot:
            self.db.increment_messages(message.author.id, message.guild.id)
        await self.process_commands(message)

async def send_log(
    bot: commands.Bot,
    title: str,
    description: str,
    log_type: str = "room",  # room, transfer, или love
    color: int = 0x2b2d31
):
    """
    Отправка лога в специальный канал
    log_type: "room" для логов комнат, "transfer" для логов переводов, "love" для логов любовных комнат
    """
    try:
        # Выбираем канал в зависимости от типа лога
        if log_type == "room":
            channel_id = ROOM_LOG_CHANNEL_ID
        elif log_type == "transfer":
            channel_id = TRANSFER_LOG_CHANNEL_ID
        else:  # love
            channel_id = LOVE_LOG_CHANNEL_ID
            
        log_channel = bot.get_channel(channel_id)
        
        if log_channel:
            embed = discord.Embed(
                title=title,
                description=description,
                color=color,
                timestamp=discord.utils.utcnow()
            )
            await log_channel.send(embed=embed)
    except Exception as e:
        print(f"[ERROR] Failed to send {log_type} log: {str(e)}")

bot = Bot()

@bot.tree.command(
    name="avatar",
    description="Показывает аватар пользователя"
)
@app_commands.describe(
    user="Выберите пользователя, чей аватар хотите посмотреть"
)
async def avatar(interaction: discord.Interaction, user: discord.User):
    avatar_url = user.display_avatar.url
    
    embed = discord.Embed(
        title=f"Аватар пользователя {user.name}"
    )
    embed.set_image(url=avatar_url)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(
    name="balance",
    description="Показывает баланс пользователя"
)
@app_commands.describe(
    user="Выберите пользователя (необязательно)"
)
async def balance(
    interaction: discord.Interaction, 
    user: discord.User = None
):
    # Если пользователь не указан, показываем баланс автора команды
    target_user = user if user else interaction.user
    user_balance = bot.db.get_balance(target_user.id)
                                                                                                                                                                                                                                                                                            
    embed = discord.Embed(
        title="Текущий баланс —",
        description=target_user.name,
        color=0x2b2d31
    )
    
    embed.add_field(
        name=f"⠀⠀{CURRENCY_COINS}:⠀⠀",
        value=f"```⠀{user_balance['coins']}⠀```",
        inline=True
    )
    
    embed.add_field(
        name=f"⠀⠀{CURRENCY_DIAMONDS}:⠀⠀",
        value=f"```⠀{user_balance['diamonds']}⠀```",
        inline=True
    )
    
    embed.set_thumbnail(url=target_user.display_avatar.url)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(
    name="addm",
    description="Добавить валюту пользователю"
)
@app_commands.guilds(bot.GUILD)  # Используем GUILD из экземпляра бота
@app_commands.describe(
    user="Выберите пользователя",
    currency_type="Выберите тип валюты",
    amount="Количество валюты для добавления"
)
@app_commands.choices(currency_type=[
    app_commands.Choice(name=CURRENCY_COINS, value="coins"),
    app_commands.Choice(name=CURRENCY_DIAMONDS, value="diamonds")
])
async def addm(
    interaction: discord.Interaction,
    user: discord.User,
    currency_type: app_commands.Choice[str],
    amount: int
):
    # Проверяем права администратора
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "У вас нет прав для использования этой команды!",
            ephemeral=True
        )
        return

    if amount <= 0:
        await interaction.response.send_message(
            "Количество должно быть положительным числом!",
            ephemeral=True
        )
        return

    new_balance = bot.db.add_currency(user.id, currency_type.value, amount)
    
    currency_name = CURRENCY_COINS if currency_type.value == "coins" else CURRENCY_DIAMONDS
    current_amount = new_balance["coins"] if currency_type.value == "coins" else new_balance["diamonds"]
    
    await interaction.response.send_message(
        f"Добавлено {amount} {currency_name} пользователю {user.name}\n"
        f"Текущий баланс: {current_amount} {currency_name}",
        ephemeral=True
    )

@bot.tree.command(
    name="banner",
    description="Показывает баннер пользователя"
)
@app_commands.guilds(bot.GUILD)  # Добавляем регистрацию для конкретного сервера
@app_commands.describe(
    user="Выберите пользователя, чей баннер хотите посмотреть"
)
async def banner(interaction: discord.Interaction, user: discord.User):
    # Получаем полную информацию о пользователе
    user = await bot.fetch_user(user.id)
    
    # Проверяем есть ли у пользователя баннер
    if user.banner is None:
        await interaction.response.send_message(
            f"У пользователя {user.name} нет баннера",
            ephemeral=True
        )
        return
    
    banner_url = user.banner.url
    
    embed = discord.Embed(
        title=f"Баннер пользователя {user.name}"
    )
    embed.set_image(url=banner_url)
    
    await interaction.response.send_message(embed=embed)

class CoinflipView(discord.ui.View):
    def __init__(self, amount: int, user_balance: dict, user: discord.User):
        super().__init__(timeout=BUTTON_TIMEOUT)
        self.amount = amount
        self.user_balance = user_balance
        self.user = user
        self.result = random.choice(["Орёл", "Решка"])

    @discord.ui.button(label="Орел", style=discord.ButtonStyle.secondary)
    async def heads_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_game(interaction, "Орёл")

    @discord.ui.button(label="Решка", style=discord.ButtonStyle.secondary)
    async def tails_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_game(interaction, "Решка")

    async def process_game(self, interaction: discord.Interaction, choice: Literal["Орёл", "Решка"]):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Это не ваша игра!", ephemeral=True)
            return

        if choice == self.result:
            win_amount = self.amount * 2
            new_balance = bot.db.add_currency(interaction.user.id, "coins", win_amount)
            embed = discord.Embed(
                title="Сыграть в монетку",
                description=f"<@{interaction.user.id}>, выпал {self.result},\nВы выиграли {win_amount} {EMOJI_COINS}",
                color=0x2b2d31
            )
        else:
            new_balance = bot.db.add_currency(interaction.user.id, "coins", -self.amount)
            embed = discord.Embed(
                title="Сыграть в монетку",
                description=f"<@{interaction.user.id}>, выпал {self.result},\nВы проиграли {self.amount} {EMOJI_COINS}",
                color=0x2b2d31
            )

        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        # Отправляем сообщение без view, чтобы убрать кнопки
        await interaction.response.edit_message(embed=embed, view=None)

@bot.tree.command(
    name="coinflip",
    description="Сыграть в монетку"
)
@app_commands.describe(
    amount="Сумма ставки (от 50 до 50000)"
)
@app_commands.guilds(bot.GUILD)
async def coinflip(interaction: discord.Interaction, amount: int):
    if amount < 50 or amount > 50000:
        await interaction.response.send_message(
            "Ставка должна быть от 50 до 50000 монет!",
            ephemeral=True
        )
        return

    user_balance = bot.db.get_balance(interaction.user.id)
    if user_balance["coins"] < amount:
        await interaction.response.send_message(
            f"У вас недостаточно {CURRENCY_COINS} для такой ставки!",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="Сыграть в монетку",
        description=f"<@{interaction.user.id}>, выберите\nсторону на которую хотите\nпоставить ваши {amount} {EMOJI_COINS}",
        color=0x2b2d31
    )
    
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    view = CoinflipView(amount, user_balance, interaction.user)
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(
    name="convert",
    description=f"Конвертировать {CURRENCY_DIAMONDS} в {CURRENCY_COINS}"
)
@app_commands.describe(
    amount=f"Количество {CURRENCY_DIAMONDS} для конвертации"
)
@app_commands.guilds(bot.GUILD)
async def convert(interaction: discord.Interaction, amount: int):
    if amount <= 0:
        await interaction.response.send_message(
            f"Количество {CURRENCY_DIAMONDS} должно быть положительным числом!",
            ephemeral=True
        )
        return

    # Проверяем баланс пользователя
    user_balance = bot.db.get_balance(interaction.user.id)
    if user_balance["diamonds"] < amount:
        await interaction.response.send_message(
            f"У вас недостаточно {CURRENCY_DIAMONDS} для конвертации!",
            ephemeral=True
        )
        return

    # Рассчитываем количество монет, которое получит пользователь
    coins_to_receive = amount * CONVERSION_RATE

    # Снимаем звезды и добавляем монеты
    bot.db.add_currency(interaction.user.id, "diamonds", -amount)
    new_balance = bot.db.add_currency(interaction.user.id, "coins", coins_to_receive)

    embed = discord.Embed(
        title="Конвертация валюты",
        description=f"<@{interaction.user.id}>, вы успешно конвертировали:\n{amount} {EMOJI_DIAMONDS} ➜ {coins_to_receive} {EMOJI_COINS}",
        color=0x2b2d31
    )

    embed.add_field(
        name=f"⠀⠀{CURRENCY_COINS}:⠀⠀",
        value=f"```⠀{new_balance['coins']}⠀```",
        inline=True
    )
    
    embed.add_field(
        name=f"⠀⠀{CURRENCY_DIAMONDS}:⠀⠀",
        value=f"```⠀{new_balance['diamonds']}⠀```",
        inline=True
    )

    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

class DuelView(discord.ui.View):
    def __init__(self, amount: int, challenger: discord.User, target: discord.User):
        super().__init__(timeout=DUEL_TIMEOUT)
        self.amount = amount
        self.challenger = challenger
        self.target = target
        self.result = None
        self.message = None

    async def on_timeout(self):
        # Создаем embed для таймаута
        embed = discord.Embed(
            title="Дуэль",
            description=f"<@{self.challenger.id}>, на Вашу дуэль\nникто не ответил",
            color=0x2b2d31
        )
        embed.set_thumbnail(url=self.challenger.display_avatar.url)
        
        # Проверяем, что сообщение существует
        if self.message:
            try:
                await self.message.edit(embed=embed, view=None)
            except discord.NotFound:
                pass  # Игнорируем ошибку, если сообщение было удалено

    @discord.ui.button(label="Присоединиться", style=discord.ButtonStyle.blurple)
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target.id:
            await interaction.response.send_message("Это не ваша дуэль!", ephemeral=True)
            return

        # Проверяем баланс обоих игроков
        challenger_balance = bot.db.get_balance(self.challenger.id)
        target_balance = bot.db.get_balance(self.target.id)

        if challenger_balance["coins"] < self.amount or target_balance["coins"] < self.amount:
            await interaction.response.edit_message(
                content="У одного из игроков недостаточно монет для дуэли!",
                embed=None,
                view=None
            )
            return

        # Определяем победителя
        winner = random.choice([self.challenger, self.target])
        loser = self.target if winner == self.challenger else self.challenger

        # Обновляем балансы
        bot.db.add_currency(winner.id, "coins", self.amount)
        bot.db.add_currency(loser.id, "coins", -self.amount)

        # Создаем embed с результатом
        embed = discord.Embed(
            title="Дуэль",
            description=f"<@{winner.id}>, выиграл {self.amount} {EMOJI_COINS}",
            color=0x2b2d31
        )
        embed.set_thumbnail(url=winner.display_avatar.url)

        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="❌", style=discord.ButtonStyle.red)
    async def decline_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target.id:
            await interaction.response.send_message("Это не ваша дуэль!", ephemeral=True)
            return

        # Создаем embed для отказа
        embed = discord.Embed(
            title="Дуэль",
            description=f"<@{self.target.id}> отказался от дуэли",
            color=0x2b2d31
        )
        embed.set_thumbnail(url=self.target.display_avatar.url)

        await interaction.response.edit_message(embed=embed, view=None)

@bot.tree.command(
    name="duel",
    description="Вызвать игрока на дуэль"
)
@app_commands.describe(
    user="Выберите игрока для дуэли",
    amount="Сумма ставки"
)
@app_commands.guilds(bot.GUILD)
async def duel(interaction: discord.Interaction, user: discord.User, amount: int):
    if user.id == interaction.user.id:
        await interaction.response.send_message(
            "Вы не можете вызвать на дуэль самого себя!",
            ephemeral=True
        )
        return

    if amount < 50:
        await interaction.response.send_message(
            "Минимальная ставка 50 монет!",
            ephemeral=True
        )
        return

    # Проверяем баланс вызывающего
    challenger_balance = bot.db.get_balance(interaction.user.id)
    if challenger_balance["coins"] < amount:
        await interaction.response.send_message(
            f"У вас недостаточно {CURRENCY_COINS} для такой ставки!",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="Дуэль",
        description=f"<@{interaction.user.id}> создал дуэль на\n{amount} {EMOJI_COINS} с пользователем\n<@{user.id}>",
        color=0x2b2d31
    )
    embed.set_thumbnail(url=interaction.user.display_avatar.url)

    view = DuelView(amount, interaction.user, user)
    await interaction.response.send_message(embed=embed, view=view)
    
    # Сохраняем сообщение после его отправки
    view.message = await interaction.original_response()

@bot.tree.command(
    name="give",
    description=f"Передать валюту другому пользователю"
)
@app_commands.describe(
    user="Выберите пользователя",
    currency_type="Выберите тип валюты",
    amount="Количество для передачи"
)
@app_commands.choices(currency_type=[
    app_commands.Choice(name=CURRENCY_COINS, value="coins"),
    app_commands.Choice(name=CURRENCY_DIAMONDS, value="diamonds")
])
async def give(
    interaction: discord.Interaction,
    user: discord.User,
    currency_type: app_commands.Choice[str],
    amount: int
):
    try:
        # Проверяем, не пытается ли пользователь передать валюту самому себе
        if user.id == interaction.user.id:
            await interaction.response.send_message(
                "Вы не можете передать валюту самому себе!",
                ephemeral=True
            )
            return

        # Проверяем корректность суммы
        if amount <= 0:
            await interaction.response.send_message(
                "Сумма должна быть положительным числом!",
                ephemeral=True
            )
            return

        # Получаем баланс отправителя
        sender_balance = bot.db.get_balance(interaction.user.id)
        
        # Определяем тип валюты и эмодзи
        currency_name = CURRENCY_COINS if currency_type.value == "coins" else CURRENCY_DIAMONDS
        emoji = EMOJI_COINS if currency_type.value == "coins" else EMOJI_DIAMONDS
        
        # Проверяем достаточно ли средств
        if sender_balance[currency_type.value] < amount:
            await interaction.response.send_message(
                f"У вас недостаточно {currency_name} для передачи!",
                ephemeral=True
            )
            return

        # Рассчитываем комиссию
        fee = int(amount * TRANSFER_FEE / 100)
        amount_after_fee = amount - fee

        # Выполняем передачу
        bot.db.add_currency(interaction.user.id, currency_type.value, -amount)
        bot.db.add_currency(user.id, currency_type.value, amount_after_fee)

        # Отправляем сообщение отправителю
        embed = discord.Embed(
            title="Передача выполнена",
            description=(
                f"Вы передали {amount} {emoji}\n"
                f"Комиссия: {fee} {emoji}\n"
                f"Получатель: {user.mention}"
            ),
            color=0x2b2d31
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)

        # Отправляем сообщение получателю
        try:
            receiver_embed = discord.Embed(
                title="Получена валюта",
                description=(
                    f"От: {interaction.user.mention}\n"
                    f"Сумма: {amount_after_fee} {emoji}"
                ),
                color=0x2b2d31
            )
            receiver_embed.set_thumbnail(url=interaction.user.display_avatar.url)
            await user.send(embed=receiver_embed)
        except:
            pass  # Если у получателя закрыты личные сообщения

        # Отправляем лог
        log_embed = discord.Embed(
            title=f"Передача {currency_name}",
            description=(
                f"**От:** {interaction.user.mention} (`{interaction.user.id}`)\n"
                f"**Кому:** {user.mention} (`{user.id}`)\n"
                f"**Сумма:** {amount} {emoji}\n"
                f"**Комиссия:** {fee} {emoji}\n"
                f"**Получено:** {amount_after_fee} {emoji}"
            ),
            color=0x2b2d31,
            timestamp=discord.utils.utcnow()
        )
        log_embed.set_thumbnail(url=interaction.user.display_avatar.url)
        
        await send_log(
            bot,
            f"Передача {currency_name}",
            log_embed.description,
            log_type="transfer",
            color=0x2b2d31
        )

    except Exception as e:
        print(f"[ERROR] Error in give command: {str(e)}")
        await interaction.response.send_message(
            f"Произошла ошибка при передаче: {str(e)}",
            ephemeral=True
        )

class RolesView(discord.ui.View):
    def __init__(self, user: discord.User, roles: list):
        super().__init__(timeout=BUTTON_TIMEOUT)
        self.user = user
        self.roles = roles
        
        # Создаем кнопки для каждой роли
        for i in range(min(len(roles), 5)):
            button = discord.ui.Button(
                label=str(i + 1),
                style=discord.ButtonStyle.secondary,
                custom_id=str(i),
                row=0
            )
            button.callback = self.button_callback
            self.add_item(button)
        
        # Добавляем кнопку "Назад"
        back_button = discord.ui.Button(
            label="Назад",
            style=discord.ButtonStyle.red,
            row=1
        )
        back_button.callback = self.back_button_callback
        self.add_item(back_button)

    async def button_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Это не ваш инвентарь!", ephemeral=True)
            return

        # Получаем индекс нажатой кнопки
        button_idx = int(interaction.data["custom_id"])
        if button_idx >= len(self.roles):
            return

        role_id, is_enabled, is_owner = self.roles[button_idx]
        role = interaction.guild.get_role(role_id)
        if role:
            new_state = not is_enabled
            bot.db.toggle_role(self.user.id, role_id, interaction.guild.id, new_state)
            
            try:
                if new_state:
                    await self.user.add_roles(role)
                else:
                    await self.user.remove_roles(role)

                # Обновляем список ролей
                self.roles = bot.db.get_user_roles(self.user.id, interaction.guild.id)
                
                # Обновляем эмбед
                description = "Ваши личные роли:\n\n"
                for i, (r_id, r_enabled, r_owner) in enumerate(self.roles[:5], 1):
                    r = interaction.guild.get_role(r_id)
                    if r:
                        status = "🟢" if r_enabled else "🔴"
                        owner_tag = " (owner)" if r_owner else ""
                        description += f"{i}) {r.mention}{owner_tag} {status}\n"

                embed = discord.Embed(
                    title="Инвентарь",
                    description=description,
                    color=0x2b2d31
                )
                embed.set_thumbnail(url=self.user.display_avatar.url)
                
                await interaction.response.edit_message(embed=embed, view=self)

            except discord.Forbidden:
                await interaction.response.send_message(
                    "У бота недостаточно прав для управления ролями!",
                    ephemeral=True
                )
            except Exception as e:
                await interaction.response.send_message(
                    f"Произошла ошибка: {str(e)}",
                    ephemeral=True
                )

    async def back_button_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Это не ваш инвентарь!", ephemeral=True)
            return

        embed = discord.Embed(
            title="Инвентарь",
            description=f"Какой из инвентарей Вы хотите\nпосмотреть?",
            color=0x2b2d31
        )
        embed.set_thumbnail(url=self.user.display_avatar.url)
        
        await interaction.response.edit_message(embed=embed, view=InventoryView(self.user))

class InventoryView(discord.ui.View):
    def __init__(self, user: discord.User):
        super().__init__(timeout=BUTTON_TIMEOUT)
        self.user = user

    @discord.ui.button(label="Личные роли", style=discord.ButtonStyle.secondary)
    async def roles_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Это не ваш инвентарь!", ephemeral=True)
            return

        try:
            # Получаем список ролей пользователя
            user_roles = bot.db.get_user_roles(self.user.id, interaction.guild.id)
            
            if not user_roles:
                await interaction.response.send_message(
                    "У вас нет личных ролей!",
                    ephemeral=True
                )
                return

            description = "Ваши личные роли:\n\n"
            for i, (role_id, is_enabled, is_owner) in enumerate(user_roles[:5], 1):
                role = interaction.guild.get_role(role_id)
                if role:
                    status = "🟢" if is_enabled else "🔴"
                    owner_tag = " (owner)" if is_owner else ""
                    description += f"{i}) {role.mention}{owner_tag} {status}\n"

            embed = discord.Embed(
                title="Инвентарь",
                description=description,
                color=0x2b2d31
            )
            embed.set_thumbnail(url=self.user.display_avatar.url)
            
            # Создаем новый view и передаем в него список ролей
            view = RolesView(self.user, user_roles)
            await interaction.response.edit_message(embed=embed, view=view)
            
        except Exception as e:
            print(f"Ошибка при отображении ролей: {e}")
            await interaction.response.send_message(
                "Произошла ошибка при загрузке ролей!",
                ephemeral=True
            )

    @discord.ui.button(label="Личные комнаты", style=discord.ButtonStyle.secondary)
    async def rooms_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Это не ваш инвентарь!", ephemeral=True)
            return

        try:
            # Получаем список комнат пользователя
            rooms = bot.db.get_user_rooms(self.user.id, interaction.guild.id)
            
            if not rooms:
                await interaction.response.send_message(
                    "У вас нет личных комнат!",
                    ephemeral=True
                )
                return

            description = "Ваши личные комнаты:\n\n"
            for room_id, voice_id, role_id, name, is_owner, is_coowner in rooms:
                voice_channel = interaction.guild.get_channel(voice_id)
                if voice_channel:
                    status = "👑" if is_owner else "⭐" if is_coowner else "👤"
                    description += f"{status} {voice_channel.mention}\n"

            embed = discord.Embed(
                title="Инвентарь",
                description=description,
                color=0x2b2d31
            )
            embed.set_thumbnail(url=self.user.display_avatar.url)
            await interaction.response.edit_message(embed=embed, view=self)

        except Exception as e:
            print(f"[ERROR] Error in rooms_button: {str(e)}")
            await interaction.response.send_message(
                f"Произошла ошибка: {str(e)}",
                ephemeral=True
            )

    @discord.ui.button(label="Предметы", style=discord.ButtonStyle.secondary)
    async def items_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Это не ваш инвентарь!", ephemeral=True)
            return

        # Здесь будет логика отображения предметов
        embed = discord.Embed(
            title="Инвентарь",
            description="Ваши предметы:",
            color=0x2b2d31
        )
        embed.set_thumbnail(url=self.user.display_avatar.url)
        
        await interaction.response.edit_message(embed=embed)

@bot.tree.command(
    name="inventory",
    description="Просмотр вашего инвентаря"
)
@app_commands.guilds(bot.GUILD)
async def inventory(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Инвентарь",
        description=f"Какой из инвентарей Вы хотите\nпосмотреть?",
        color=0x2b2d31
    )
    embed.set_thumbnail(url=interaction.user.display_avatar.url)

    view = InventoryView(interaction.user)
    await interaction.response.send_message(embed=embed, view=view)
    view.message = await interaction.original_response()

class RoleManagerView(discord.ui.View):
    def __init__(self, user: discord.User, role_id: int):
        super().__init__(timeout=BUTTON_TIMEOUT)
        self.user = user
        self.role_id = role_id

    @discord.ui.button(label="Сменить цвет", style=discord.ButtonStyle.secondary)
    async def color_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Это не ваша роль!", ephemeral=True)
            return

        # Проверяем баланс
        user_balance = bot.db.get_balance(interaction.user.id)
        if user_balance["coins"] < ROLE_COLOR_PRICE:
            await interaction.response.send_message(
                f"Недостаточно монет! Необходимо: {ROLE_COLOR_PRICE} {EMOJI_COINS}",
                ephemeral=True
            )
            return

        # Создаем модальное окно для ввода цвета
        class ColorModal(discord.ui.Modal, title="Смена цвета роли"):
            color = discord.ui.TextInput(
                label="Введите цвет в HEX формате",
                placeholder="#ff0000",
                min_length=7,
                max_length=7
            )

            async def on_submit(self, interaction: discord.Interaction):
                try:
                    color_str = str(self.color)
                    if not color_str.startswith('#'):
                        await interaction.response.send_message(
                            "Цвет должен начинаться с #!",
                            ephemeral=True
                        )
                        return

                    color_int = int(color_str[1:], 16)
                    role = interaction.guild.get_role(self.view.role_id)
                    
                    # Снимаем плату и меняем цвет
                    bot.db.add_currency(interaction.user.id, "coins", -ROLE_COLOR_PRICE)
                    await role.edit(color=discord.Color(color_int))
                    
                    embed = discord.Embed(
                        title="Управление ролью",
                        description=f"Цвет роли {role.mention} успешно изменен!\nСписано {ROLE_COLOR_PRICE} {EMOJI_COINS}",
                        color=discord.Color(color_int)
                    )
                    embed.set_thumbnail(url=interaction.user.display_avatar.url)
                    await interaction.response.send_message(embed=embed)
                
                except ValueError:
                    await interaction.response.send_message(
                        "Неверный формат цвета!",
                        ephemeral=True
                    )

        modal = ColorModal()
        modal.view = self
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Сменить название", style=discord.ButtonStyle.secondary)
    async def name_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Это не ваша роль!", ephemeral=True)
            return

        # Проверяем баланс
        user_balance = bot.db.get_balance(interaction.user.id)
        if user_balance["coins"] < ROLE_NAME_PRICE:
            await interaction.response.send_message(
                f"Недостаточно монет! Необходимо: {ROLE_NAME_PRICE} {EMOJI_COINS}",
                ephemeral=True
            )
            return

        # Создаем модальное окно для ввода названия
        class NameModal(discord.ui.Modal, title="Смена названия роли"):
            name = discord.ui.TextInput(
                label="Введите новое название роли",
                min_length=1,
                max_length=100
            )

            async def on_submit(self, interaction: discord.Interaction):
                role = interaction.guild.get_role(self.view.role_id)
                
                # Снимаем плату и меняем название
                bot.db.add_currency(interaction.user.id, "coins", -ROLE_NAME_PRICE)
                await role.edit(name=str(self.name))
                
                embed = discord.Embed(
                    title="Управление ролью",
                    description=f"Название роли {role.mention} успешно изменено!\nСписано {ROLE_NAME_PRICE} {EMOJI_COINS}",
                    color=role.color
                )
                embed.set_thumbnail(url=interaction.user.display_avatar.url)
                await interaction.response.send_message(embed=embed)

        modal = NameModal()
        modal.view = self
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Выдать роль", style=discord.ButtonStyle.secondary)
    async def give_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Это не ваша роль!", ephemeral=True)
            return

        class GiveModal(discord.ui.Modal, title="Выдача роли"):
            user_id = discord.ui.TextInput(
                label="Введите ID пользователя или @упоминание",
                min_length=1
            )

            async def on_submit(self, interaction: discord.Interaction):
                try:
                    target_id = ''.join(filter(str.isdigit, str(self.user_id)))
                    target_user = await interaction.guild.fetch_member(int(target_id))
                    role = interaction.guild.get_role(self.view.role_id)
                    
                    await target_user.add_roles(role)
                    bot.db.add_user_role(target_user.id, role.id, interaction.guild.id, is_owner=False)
                    
                    embed = discord.Embed(
                        title="Управление ролью",
                        description=f"Роль {role.mention} выдана пользователю {target_user.mention}",
                        color=role.color
                    )
                    embed.set_thumbnail(url=interaction.user.display_avatar.url)
                    await interaction.response.send_message(embed=embed)
                
                except (ValueError, discord.NotFound):
                    await interaction.response.send_message(
                        "Пользователь не найден!",
                        ephemeral=True
                    )

        modal = GiveModal()
        modal.view = self
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Удалить роль", style=discord.ButtonStyle.danger)
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Это не ваша роль!", ephemeral=True)
            return

        role = interaction.guild.get_role(self.role_id)
        bot.db.delete_role(role.id, interaction.guild.id)
        await role.delete()
        
        embed = discord.Embed(
            title="Управление ролью",
            description="Роль успешно удалена!",
            color=0x2b2d31
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)

        # Перед удалением добавляем лог
        await send_log(
            bot,
            "Удалена комната",
            f"**Название:** {room_data['name']}\n"
            f"**Владелец:** {interaction.user.mention} (`{interaction.user.id}`)",
            log_type="room",
            color=0xED4245  # Красный цвет для удаления
        )

class RoleListView(discord.ui.View):
    def __init__(self, user: discord.User, roles: list):
        super().__init__(timeout=BUTTON_TIMEOUT)
        self.user = user
        self.roles = roles
        
        # Создаем кнопки для каждой роли
        for i, (role_id, _, is_owner) in enumerate(roles[:5]):
            if is_owner:  # Показываем только те роли, где пользователь owner
                button = discord.ui.Button(
                    label=f"Роль {i+1}",
                    style=discord.ButtonStyle.secondary,
                    custom_id=str(role_id),
                    row=0
                )
                button.callback = self.role_button_callback
                self.add_item(button)

    async def role_button_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Это не ваш инвентарь!", ephemeral=True)
            return

        role_id = int(interaction.data["custom_id"])
        role = interaction.guild.get_role(role_id)
        
        if not role:
            await interaction.response.send_message("Роль не найдена!", ephemeral=True)
            return

        embed = discord.Embed(
            title="Управление ролью",
            description=f"Выберите действие для роли {role.mention}",
            color=role.color
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        
        view = RoleManagerView(interaction.user, role_id)
        await interaction.response.edit_message(embed=embed, view=view)

@bot.tree.command(
    name="role",
    description="Управление личными ролями"
)
@app_commands.describe(
    action="Выберите действие"
)
@app_commands.choices(action=[
    app_commands.Choice(name="create", value="create"),
    app_commands.Choice(name="manage", value="manage")
])
@app_commands.guilds(bot.GUILD)
async def role(
    interaction: discord.Interaction,
    action: app_commands.Choice[str]
):
    if action.value == "manage":
        # Получаем список ролей пользователя
        roles = bot.db.get_user_roles(interaction.user.id, interaction.guild.id)
        owned_roles = [(role_id, is_enabled, is_owner) for role_id, is_enabled, is_owner in roles if is_owner]

        if not owned_roles:
            await interaction.response.send_message(
                "У вас нет личных ролей, которыми вы владеете!",
                ephemeral=True
            )
            return

        description = "Ваши личные роли:\n\n"
        for i, (role_id, is_enabled, _) in enumerate(owned_roles[:5], 1):
            role = interaction.guild.get_role(role_id)
            if role:
                status = "🟢" if is_enabled else "🔴"
                description += f"{i}) {role.mention} {status}\n"

        embed = discord.Embed(
            title="Управление ролями",
            description=description,
            color=0x2b2d31
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        
        view = RoleListView(interaction.user, owned_roles)
        await interaction.response.send_message(embed=embed, view=view)

    elif action.value == "create":
        # Проверяем баланс пользователя
        user_balance = bot.db.get_balance(interaction.user.id)
        if user_balance["coins"] < ROLE_CREATE_PRICE:
            await interaction.response.send_message(
                f"Недостаточно монет! Необходимо: {ROLE_CREATE_PRICE} {EMOJI_COINS}",
                ephemeral=True
            )
            return

        # Создаем модальное окно для создания роли
        class CreateRoleModal(discord.ui.Modal, title="Создание роли"):
            name = discord.ui.TextInput(
                label="Название роли",
                min_length=1,
                max_length=100
            )
            color = discord.ui.TextInput(
                label="Цвет роли в HEX формате",
                placeholder="#ff0000",
                min_length=7,
                max_length=7
            )

            async def on_submit(self, interaction: discord.Interaction):
                try:
                    color_str = str(self.color)
                    if not color_str.startswith('#'):
                        await interaction.response.send_message(
                            "Цвет должен начинаться с #!",
                            ephemeral=True
                        )
                        return

                    color_int = int(color_str[1:], 16)
                    
                    # Снимаем плату за создание роли
                    bot.db.add_currency(interaction.user.id, "coins", -ROLE_CREATE_PRICE)
                    
                    new_role = await interaction.guild.create_role(
                        name=str(self.name),
                        color=discord.Color(color_int),
                        reason=f"Личная роль создана пользователем {interaction.user.name}"
                    )
                    
                    # Сначала добавляем роль в базу данных
                    bot.db.add_role(
                        role_id=new_role.id,
                        guild_id=interaction.guild.id,
                        owner_id=interaction.user.id
                    )
                    
                    # Затем выдаем роль пользователю
                    await interaction.user.add_roles(new_role)

                    embed = discord.Embed(
                        title="Создание роли",
                        description=f"Роль {new_role.mention} успешно создана!\nСписано {ROLE_CREATE_PRICE} {EMOJI_COINS}",
                        color=new_role.color
                    )
                    embed.set_thumbnail(url=interaction.user.display_avatar.url)
                    await interaction.response.send_message(embed=embed)

                except ValueError:
                    await interaction.response.send_message(
                        "Неверный формат цвета!",
                        ephemeral=True
                    )
                except discord.Forbidden:
                    await interaction.response.send_message(
                        "У бота недостаточно прав для создания роли!",
                        ephemeral=True
                    )

        modal = CreateRoleModal()
        await interaction.response.send_modal(modal)

@bot.tree.command(
    name="addroom",
    description="Создать приватную комнату [ADMIN]"
)
@app_commands.describe(
    name="Название комнаты",
    owner="ID владельца комнаты"
)
@app_commands.guilds(bot.GUILD)
async def addroom(
    interaction: discord.Interaction,
    name: str,
    owner: str
):
    # Проверяем права администратора
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "У вас нет прав для использования этой команды!",
            ephemeral=True
        )
        return

    try:
        # Получаем категорию
        category = interaction.guild.get_channel(PRIVATE_CATEGORY_ID)
        if not category:
            await interaction.response.send_message(
                "Категория для приватных комнат не найдена!",
                ephemeral=True
            )
            return

        # Получаем владельца
        try:
            owner_id = int(''.join(filter(str.isdigit, owner)))
            owner_member = await interaction.guild.fetch_member(owner_id)
            if not owner_member:
                raise ValueError
        except (ValueError, discord.NotFound):
            await interaction.response.send_message(
                "Указанный владелец не найден!",
                ephemeral=True
            )
            return

        # Создаем роль с тем же названием, что и комната
        role = await interaction.guild.create_role(
            name=name,
            reason=f"Роль для приватной комнаты {name}"
        )

        # Выдаем роль владельцу
        await owner_member.add_roles(role)

        # Создаем канал
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(
                view_channel=False,
                connect=False
            ),
            role: discord.PermissionOverwrite(
                view_channel=True,
                connect=True,
                speak=True
            ),
            owner_member: discord.PermissionOverwrite(
                view_channel=True,
                connect=True,
                speak=True,
                mute_members=True,
                deafen_members=True,
                move_members=True,
                manage_channels=True
            )
        }

        voice_channel = await interaction.guild.create_voice_channel(
            name=name,
            category=category,
            overwrites=overwrites,
            reason=f"Приватная комната создана для {owner_member.name}"
        )

        # Сохраняем информацию в базе данных
        bot.db.add_private_room(
            room_id=voice_channel.id,  # Используем ID голосового канала как основной
            voice_id=voice_channel.id,
            role_id=role.id,
            guild_id=interaction.guild.id,
            owner_id=owner_member.id,
            name=name
        )

        embed = discord.Embed(
            title="Приватная комната создана",
            description=(
                f"**Владелец:** {owner_member.mention}\n"
                f"**Голосовой канал:** {voice_channel.mention}\n"
                f"**Роль доступа:** {role.mention}"
            ),
            color=0x2b2d31
        )
        embed.set_thumbnail(url=owner_member.display_avatar.url)

        await interaction.response.send_message(embed=embed)

        # После успешного создания добавляем лог
        await send_log(
            bot,
            "Создана новая комната",
            f"**Название:** {name}\n"
            f"**Владелец:** {interaction.user.mention} (`{interaction.user.id}`)\n"
            f"**Текстовый канал:** {text_channel.mention}\n"
            f"**Голосовой канал:** {voice_channel.mention}",
            log_type="room",
            color=0x57F287  # Зеленый цвет для создания
        )

    except discord.Forbidden:
        await interaction.response.send_message(
            "У бота недостаточно прав для создания каналов или ролей!",
            ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(
            f"Произошла ошибка при создании комнаты: {str(e)}",
            ephemeral=True
        )

class UserSelect(discord.ui.UserSelect):
    def __init__(self, placeholder: str):
        super().__init__(
            placeholder=placeholder,
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        print(f"[DEBUG] UserSelect callback triggered by {interaction.user}")
        if self.view is not None:
            try:
                print(f"[DEBUG] Calling handle_user_select with user {self.values[0]}")
                await self.view.handle_user_select(interaction, self.values[0])
            except Exception as e:
                print(f"[ERROR] Error in UserSelect callback: {str(e)}")
                await interaction.response.send_message(
                    f"Произошла ошибка при обработке выбора: {str(e)}",
                    ephemeral=True
                )

    async def handle_user_select(self, interaction: discord.Interaction, selected_user: discord.User):
        print(f"[DEBUG] handle_user_select started. Action: {self.action}")
        
        if interaction.user.id != self.user.id:
            print(f"[DEBUG] User mismatch: {interaction.user.id} != {self.user.id}")
            await interaction.response.send_message("Это не ваше меню!", ephemeral=True)
            return

        if self.action == "give_access":
            print(f"[DEBUG] Processing give_access for user {selected_user}")
            try:
                room_data = bot.db.get_room_data(self.room_id)
                print(f"[DEBUG] Room data: {room_data}")
                
                if not room_data:
                    await interaction.response.send_message("Комната не найдена!", ephemeral=True)
                    return

                # Проверяем права на приглашение
                member_data = bot.db.get_member_data(interaction.user.id, self.room_id)
                print(f"[DEBUG] Member data: {member_data}")
                
                if not member_data or (not member_data["is_owner"] and not member_data["is_coowner"]):
                    await interaction.response.send_message(
                        "Только владелец и совладельцы могут приглашать пользователей!",
                        ephemeral=True
                    )
                    return

                # Проверяем, не состоит ли пользователь уже в комнате
                existing_member = bot.db.get_member_data(selected_user.id, self.room_id)
                print(f"[DEBUG] Existing member data: {existing_member}")
                
                if existing_member:
                    await interaction.response.send_message(
                        "Этот пользователь уже состоит в комнате!",
                        ephemeral=True
                    )
                    return

                print("[DEBUG] Creating invite embed and view")
                # Создаем приглашение
                invite_embed = discord.Embed(
                    title="Приглашение в комнату",
                    description=(
                        f"{interaction.user.mention} приглашает вас\n"
                        f"присоединиться к комнате {room_data['name']}"
                    ),
                    color=0x2b2d31
                )
                invite_embed.set_thumbnail(url=interaction.user.display_avatar.url)

                invite_view = RoomInviteView(
                    room_name=room_data['name'],
                    inviter=interaction.user,
                    room_id=self.room_id,
                    role_id=room_data['role_id'],
                    guild_id=interaction.guild_id
                )

                print("[DEBUG] Sending initial response")
                try:
                    # Сначала отправляем ответ на исходное взаимодействие
                    await interaction.response.defer(ephemeral=True)
                    
                    print("[DEBUG] Sending DM to user")
                    # Пытаемся отправить приглашение
                    await selected_user.send(embed=invite_embed, view=invite_view)
                    
                    print("[DEBUG] Updating original message")
                    # Обновляем исходное сообщение
                    success_embed = discord.Embed(
                        title="Управление комнатой",
                        description=f"Приглашение отправлено пользователю {selected_user.mention}",
                        color=0x2b2d31
                    )
                    success_embed.set_thumbnail(url=interaction.user.display_avatar.url)
                    
                    # Удаляем селект
                    for item in self.children[:]:
                        if isinstance(item, discord.ui.UserSelect):
                            self.remove_item(item)
                    
                    await interaction.followup.edit_message(
                        message_id=interaction.message.id,
                        embed=success_embed,
                        view=self
                    )
                    
                    # Добавляем лог
                    await send_log(
                        bot,
                        "Отправлено приглашение в комнату",
                        f"**Комната:** {room_data['name']}\n"
                        f"**Отправитель:** {interaction.user.mention} ({interaction.user.id})\n"
                        f"**Получатель:** {selected_user.mention} ({selected_user.id})",
                        color=0xFEE75C  # Желтый цвет для ожидания ответа
                    )
                    
                except discord.Forbidden:
                    print("[DEBUG] Failed to send DM - Forbidden")
                    await interaction.followup.send(
                        f"Не удалось отправить приглашение. У пользователя {selected_user.mention} закрыты личные сообщения.",
                        ephemeral=True
                    )
                except Exception as e:
                    print(f"[ERROR] Failed to send invite: {str(e)}")
                    await interaction.followup.send(
                        f"Произошла ошибка при отправке приглашения: {str(e)}",
                        ephemeral=True
                    )

            except Exception as e:
                print(f"[ERROR] Error in give_access: {str(e)}")
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        f"Произошла ошибка: {str(e)}",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        f"Произошла ошибка: {str(e)}",
                        ephemeral=True
                    )

        elif self.action == "remove_access":
            # ... код для удаления доступа ...
            pass

        elif self.action == "add_coowner":
            # ... код для добавления совладельца ...
            pass

        elif self.action == "remove_coowner":
            # ... код для удаления совладельца ...
            pass

class RoomInviteView(discord.ui.View):
    def __init__(self, room_name: str, inviter: discord.User, room_id: int, role_id: int, guild_id: int):
        super().__init__(timeout=300)
        self.room_name = room_name
        self.inviter = inviter
        self.room_id = room_id
        self.role_id = role_id
        self.guild_id = guild_id

    @discord.ui.button(emoji="✅", style=discord.ButtonStyle.green)
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            guild = bot.get_guild(self.guild_id)
            if not guild:
                await interaction.response.send_message("Не удалось найти сервер!", ephemeral=True)
                return

            role = guild.get_role(self.role_id)
            if not role:
                await interaction.response.send_message("Не удалось найти роль!", ephemeral=True)
                return

            member = await guild.fetch_member(interaction.user.id)
            if not member:
                await interaction.response.send_message("Не удалось найти вас на сервере!", ephemeral=True)
                return
            
            await member.add_roles(role)
            bot.db.add_room_member(interaction.user.id, self.room_id, self.guild_id)
            
            embed = discord.Embed(
                title="Приглашение принято",
                description=f"Вы присоединились к комнате {self.room_name}",
                color=0x2b2d31
            )
            await interaction.response.edit_message(embed=embed, view=None)
            
            try:
                notify_embed = discord.Embed(
                    title="Приглашение принято",
                    description=f"{interaction.user.mention} принял ваше приглашение в комнату {self.room_name}",
                    color=0x2b2d31
                )
                await self.inviter.send(embed=notify_embed)
            except:
                pass

            # Добавляем лог
            await send_log(
                bot,
                "Приглашение в комнату принято",
                f"**Комната:** {self.room_name}\n"
                f"**Пригласил:** {self.inviter.mention} ({self.inviter.id})\n"
                f"**Принял:** {interaction.user.mention} ({interaction.user.id})",
                color=0x57F287  # Зеленый цвет для принятия
            )

        except Exception as e:
            await interaction.response.send_message(f"Произошла ошибка: {str(e)}", ephemeral=True)

    @discord.ui.button(emoji="❌", style=discord.ButtonStyle.red)
    async def decline_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="Приглашение отклонено",
            description=f"Вы отклонили приглашение в комнату {self.room_name}",
            color=0x2b2d31
        )
        await interaction.response.edit_message(embed=embed, view=None)
        
        try:
            notify_embed = discord.Embed(
                title="Приглашение отклонено",
                description=f"{interaction.user.mention} отклонил ваше приглашение в комнату {self.room_name}",
                color=0x2b2d31
            )
            await self.inviter.send(embed=notify_embed)
        except:
            pass

        # Добавляем лог
        await send_log(
            bot,
            "Приглашение в комнату отклонено",
            f"**Комната:** {self.room_name}\n"
            f"**Пригласил:** {self.inviter.mention} ({self.inviter.id})\n"
            f"**Отклонил:** {interaction.user.mention} ({interaction.user.id})",
            color=0xED4245  # Красный цвет для отклонения
        )

class RoomManagerView(discord.ui.View):
    def __init__(self, user: discord.User, room_id: int):
        super().__init__(timeout=BUTTON_TIMEOUT)
        self.user = user
        self.room_id = room_id
        self.action = None

    @discord.ui.button(label="Выдать доступ", style=discord.ButtonStyle.secondary)
    async def give_access_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Это не ваша комната!", ephemeral=True)
            return

        # Проверяем права на приглашение
        member_data = bot.db.get_member_data(interaction.user.id, self.room_id)
        if not member_data or (not member_data["is_owner"] and not member_data["is_coowner"]):
            await interaction.response.send_message(
                "Только владелец и совладельцы могут приглашать пользователей!",
                ephemeral=True
            )
            return

        # Очищаем предыдущие селекты
        for item in self.children[:]:
            if isinstance(item, discord.ui.UserSelect):
                self.remove_item(item)

        # Добавляем селект для выбора пользователя
        self.action = "give_access"
        select = UserSelect("Выберите пользователя для приглашения")
        self.add_item(select)

        embed = discord.Embed(
            title="Приглашение пользователя",
            description=f"@{interaction.user.name}, выберите\nпользователя, которого хотите\nпригласить в комнату",
            color=0x2b2d31
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Забрать доступ", style=discord.ButtonStyle.secondary)
    async def remove_access_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Это не ваша комната!", ephemeral=True)
            return

        # Очищаем предыдущие селекты
        for item in self.children[:]:
            if isinstance(item, discord.ui.UserSelect):
                self.remove_item(item)

        # Добавляем селект для выбора пользователя
        self.action = "remove_access"
        select = UserSelect("Выберите пользователя для удаления доступа")
        self.add_item(select)

        embed = discord.Embed(
            title="Удаление пользователя",
            description=f"@{interaction.user.name}, выберите\nпользователя, которого хотите\nудалить из комнаты",
            color=0x2b2d31
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Список участников", style=discord.ButtonStyle.secondary)
    async def members_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Это не ваша комната!", ephemeral=True)
            return

        try:
            room_data = bot.db.get_room_data(self.room_id)
            if not room_data:
                await interaction.response.send_message("Комната не найдена!", ephemeral=True)
                return

            members = bot.db.get_room_members(self.room_id)
            
            description = f"Участники комнаты {room_data['name']}:\n\n"
            
            for user_id, is_owner, is_coowner, total_time, last_join in members:
                member = interaction.guild.get_member(user_id)
                if member:
                    # Конвертируем время
                    current_time = total_time
                    if last_join:
                        try:
                            # Преобразуем строку времени в UTC datetime
                            last_join_dt = discord.utils.parse_time(last_join).replace(tzinfo=None)
                            current_time += (discord.utils.utcnow().replace(tzinfo=None) - last_join_dt).total_seconds()
                        except:
                            # В случае ошибки используем только total_time
                            pass
                        
                    hours = int(current_time // 3600)
                    minutes = int((current_time % 3600) // 60)
                    seconds = int(current_time % 60)
                    time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                    
                    # Добавляем статус
                    if is_owner:
                        status = "👑 Владелец"
                    elif is_coowner:
                        status = "⭐ Совладелец"
                    else:
                        status = "👤 Участник"
                    
                    description += f"{status} {member.mention} - {time_str}\n"

            embed = discord.Embed(
                title="Список участников",
                description=description,
                color=0x2b2d31
            )
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            
            await interaction.response.edit_message(embed=embed, view=self)

        except Exception as e:
            print(f"[ERROR] Error in members_button: {str(e)}")
            await interaction.response.send_message(
                f"Произошла ошибка: {str(e)}",
                ephemeral=True
            )

    @discord.ui.button(label="Переименовать", style=discord.ButtonStyle.secondary)
    async def rename_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Это не ваша комната!", ephemeral=True)
            return

        # Проверяем права на изменение
        member_data = bot.db.get_member_data(interaction.user.id, self.room_id)
        if not member_data or not member_data["is_owner"]:
            await interaction.response.send_message(
                "Только владелец может изменять название комнаты!",
                ephemeral=True
            )
            return

        # Проверяем баланс
        balance = bot.db.get_balance(interaction.user.id)
        if balance["coins"] < ROOM_RENAME_PRICE:
            await interaction.response.send_message(
                f"Недостаточно монет! Необходимо: {ROOM_RENAME_PRICE} {EMOJI_COINS}",
                ephemeral=True
            )
            return

        class RenameModal(discord.ui.Modal, title="Изменение названия"):
            new_name = discord.ui.TextInput(
                label=f"Новое название (Стоимость: {ROOM_RENAME_PRICE} {EMOJI_COINS})",
                min_length=1,
                max_length=32
            )

            async def on_submit(self, interaction: discord.Interaction):
                try:
                    room_data = bot.db.get_room_data(self.view.room_id)
                    if not room_data:
                        await interaction.response.send_message("Комната не найдена!", ephemeral=True)
                        return

                    # Списываем монеты
                    bot.db.add_currency(interaction.user.id, "coins", -ROOM_RENAME_PRICE)

                    # Получаем каналы и роль
                    voice_channel = interaction.guild.get_channel(room_data["voice_id"])
                    role = interaction.guild.get_role(room_data["role_id"])

                    # Обновляем названия
                    await voice_channel.edit(name=str(self.new_name))
                    await role.edit(name=str(self.new_name))

                    # Обновляем в базе данных
                    bot.db.update_room_name(self.view.room_id, str(self.new_name))

                    embed = discord.Embed(
                        title="Управление комнатой",
                        description=f"Название комнаты изменено на: {self.new_name}\nСписано: {ROOM_RENAME_PRICE} {EMOJI_COINS}",
                        color=0x2b2d31
                    )
                    embed.set_thumbnail(url=interaction.user.display_avatar.url)
                    await interaction.response.edit_message(embed=embed, view=self.view)

                    # После успешного изменения добавляем лог
                    await send_log(
                        bot,
                        "Изменено название комнаты",
                        f"**Старое название:** {room_data['name']}\n"
                        f"**Новое название:** {self.new_name}\n"
                        f"**Владелец:** {interaction.user.mention} (`{interaction.user.id}`)",
                        log_type="room",
                        color=0x3498DB  # Синий цвет для изменений
                    )

                except Exception as e:
                    await interaction.response.send_message(
                        f"Произошла ошибка: {str(e)}",
                        ephemeral=True
                    )

        modal = RenameModal()
        modal.view = self
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Изменить цвет", style=discord.ButtonStyle.secondary)
    async def color_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Это не ваша комната!", ephemeral=True)
            return

        # Проверяем права на изменение
        member_data = bot.db.get_member_data(interaction.user.id, self.room_id)
        if not member_data or not member_data["is_owner"]:
            await interaction.response.send_message(
                "Только владелец может изменять цвет роли!",
                ephemeral=True
            )
            return

        # Проверяем баланс
        balance = bot.db.get_balance(interaction.user.id)
        if balance["coins"] < ROOM_COLOR_PRICE:
            await interaction.response.send_message(
                f"Недостаточно монет! Необходимо: {ROOM_COLOR_PRICE} {EMOJI_COINS}",
                ephemeral=True
            )
            return

        class ColorModal(discord.ui.Modal, title="Изменение цвета"):
            color = discord.ui.TextInput(
                label=f"Новый цвет (HEX формат, например: #ff0000)\nСтоимость: {ROOM_COLOR_PRICE} {EMOJI_COINS}",
                min_length=7,
                max_length=7,
                placeholder="#ffffff"
            )

            async def on_submit(self, interaction: discord.Interaction):
                try:
                    room_data = bot.db.get_room_data(self.view.room_id)
                    if not room_data:
                        await interaction.response.send_message("Комната не найдена!", ephemeral=True)
                        return

                    # Проверяем формат цвета
                    color_str = str(self.color)
                    if not color_str.startswith('#') or len(color_str) != 7:
                        await interaction.response.send_message(
                            "Неверный формат цвета! Используйте HEX формат (#ff0000)",
                            ephemeral=True
                        )
                        return

                    try:
                        color_int = int(color_str[1:], 16)
                    except ValueError:
                        await interaction.response.send_message(
                            "Неверный формат цвета!",
                            ephemeral=True
                        )
                        return

                    # Списываем монеты
                    bot.db.add_currency(interaction.user.id, "coins", -ROOM_COLOR_PRICE)

                    # Изменяем цвет роли
                    role = interaction.guild.get_role(room_data["role_id"])
                    await role.edit(color=discord.Color(color_int))

                    embed = discord.Embed(
                        title="Управление комнатой",
                        description=f"Цвет роли изменен на: {color_str}\nСписано: {ROOM_COLOR_PRICE} {EMOJI_COINS}",
                        color=color_int
                    )
                    embed.set_thumbnail(url=interaction.user.display_avatar.url)
                    await interaction.response.edit_message(embed=embed, view=self.view)

                    # После успешного изменения добавляем лог
                    await send_log(
                        bot,
                        "Изменен цвет роли комнаты",
                        f"**Комната:** {room_data['name']}\n"
                        f"**Владелец:** {interaction.user.mention} (`{interaction.user.id}`)\n"
                        f"**Новый цвет:** #{hex(color_int)[2:].upper()}",
                        log_type="room",
                        color=color_int  # Используем выбранный цвет
                    )

                except Exception as e:
                    await interaction.response.send_message(
                        f"Произошла ошибка: {str(e)}",
                        ephemeral=True
                    )

        modal = ColorModal()
        modal.view = self
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Добавить совладельца", style=discord.ButtonStyle.secondary)
    async def add_coowner_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Это не ваша комната!", ephemeral=True)
            return

        # Проверяем права на изменение
        member_data = bot.db.get_member_data(interaction.user.id, self.room_id)
        if not member_data or not member_data["is_owner"]:
            await interaction.response.send_message(
                "Только владелец может назначать совладельцев!",
                ephemeral=True
            )
            return

        # Очищаем предыдущие селекты
        for item in self.children[:]:
            if isinstance(item, discord.ui.UserSelect):
                self.remove_item(item)

        # Добавляем селект для выбора пользователя
        self.action = "add_coowner"
        select = UserSelect("Выберите пользователя для назначения совладельцем")
        self.add_item(select)

        embed = discord.Embed(
            title="Добавление совладельца",
            description=f"@{interaction.user.name}, выберите\nпользователя, которого хотите\nназначить совладельцем",
            color=0x2b2d31
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Удалить совладельца", style=discord.ButtonStyle.secondary)
    async def remove_coowner_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Это не ваша комната!", ephemeral=True)
            return

        # Проверяем права на изменение
        member_data = bot.db.get_member_data(interaction.user.id, self.room_id)
        if not member_data or not member_data["is_owner"]:
            await interaction.response.send_message(
                "Только владелец может удалять совладельцев!",
                ephemeral=True
            )
            return

        # Очищаем предыдущие селекты
        for item in self.children[:]:
            if isinstance(item, discord.ui.UserSelect):
                self.remove_item(item)

        # Добавляем селект для выбора пользователя
        self.action = "remove_coowner"
        select = UserSelect("Выберите совладельца для удаления")
        self.add_item(select)

        embed = discord.Embed(
            title="Удаление совладельца",
            description=f"@{interaction.user.name}, выберите\nсовладельца, которого хотите\nудалить",
            color=0x2b2d31
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        
        await interaction.response.edit_message(embed=embed, view=self)

    async def handle_user_select(self, interaction: discord.Interaction, selected_user: discord.User):
        print(f"[DEBUG] handle_user_select started. Action: {self.action}")
        
        if interaction.user.id != self.user.id:
            print(f"[DEBUG] User mismatch: {interaction.user.id} != {self.user.id}")
            await interaction.response.send_message("Это не ваше меню!", ephemeral=True)
            return

        if self.action == "give_access":
            print(f"[DEBUG] Processing give_access for user {selected_user}")
            try:
                room_data = bot.db.get_room_data(self.room_id)
                print(f"[DEBUG] Room data: {room_data}")
                
                if not room_data:
                    await interaction.response.send_message("Комната не найдена!", ephemeral=True)
                    return

                # Проверяем, не состоит ли пользователь уже в комнате
                existing_member = bot.db.get_member_data(selected_user.id, self.room_id)
                print(f"[DEBUG] Existing member data: {existing_member}")
                
                if existing_member:
                    await interaction.response.send_message(
                        "Этот пользователь уже состоит в комнате!",
                        ephemeral=True
                    )
                    return

                print("[DEBUG] Creating invite embed and view")
                # Создаем приглашение
                invite_embed = discord.Embed(
                    title="Приглашение в комнату",
                    description=(
                        f"{interaction.user.mention} приглашает вас\n"
                        f"присоединиться к комнате {room_data['name']}"
                    ),
                    color=0x2b2d31
                )
                invite_embed.set_thumbnail(url=interaction.user.display_avatar.url)

                invite_view = RoomInviteView(
                    room_name=room_data['name'],
                    inviter=interaction.user,
                    room_id=self.room_id,
                    role_id=room_data['role_id'],
                    guild_id=interaction.guild_id
                )

                print("[DEBUG] Sending initial response")
                try:
                    # Сначала отправляем ответ на исходное взаимодействие
                    await interaction.response.defer(ephemeral=True)
                    
                    print("[DEBUG] Sending DM to user")
                    # Пытаемся отправить приглашение
                    await selected_user.send(embed=invite_embed, view=invite_view)
                    
                    print("[DEBUG] Updating original message")
                    # Обновляем исходное сообщение
                    success_embed = discord.Embed(
                        title="Управление комнатой",
                        description=f"Приглашение отправлено пользователю {selected_user.mention}",
                        color=0x2b2d31
                    )
                    success_embed.set_thumbnail(url=interaction.user.display_avatar.url)
                    
                    # Удаляем селект
                    for item in self.children[:]:
                        if isinstance(item, discord.ui.UserSelect):
                            self.remove_item(item)
                    
                    await interaction.followup.edit_message(
                        message_id=interaction.message.id,
                        embed=success_embed,
                        view=self
                    )
                    
                    # Добавляем лог
                    await send_log(
                        bot,
                        "Отправлено приглашение в комнату",
                        f"**Комната:** {room_data['name']}\n"
                        f"**Отправитель:** {interaction.user.mention} ({interaction.user.id})\n"
                        f"**Получатель:** {selected_user.mention} ({selected_user.id})",
                        color=0xFEE75C  # Желтый цвет для ожидания ответа
                    )
                    
                except discord.Forbidden:
                    print("[DEBUG] Failed to send DM - Forbidden")
                    await interaction.followup.send(
                        f"Не удалось отправить приглашение. У пользователя {selected_user.mention} закрыты личные сообщения.",
                        ephemeral=True
                    )
                except Exception as e:
                    print(f"[ERROR] Failed to send invite: {str(e)}")
                    await interaction.followup.send(
                        f"Произошла ошибка при отправке приглашения: {str(e)}",
                        ephemeral=True
                    )

            except Exception as e:
                print(f"[ERROR] Error in give_access: {str(e)}")
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        f"Произошла ошибка: {str(e)}",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        f"Произошла ошибка: {str(e)}",
                        ephemeral=True
                    )

        elif self.action == "remove_access":
            # ... код для удаления доступа ...
            pass

        elif self.action == "add_coowner":
            # ... код для добавления совладельца ...
            pass

        elif self.action == "remove_coowner":
            # ... код для удаления совладельца ...
            pass

@bot.tree.command(
    name="room",
    description="Управление приватными комнатами"
)
@app_commands.guilds(bot.GUILD)
async def room(interaction: discord.Interaction):
    try:
        # Получаем список комнат пользователя
        rooms = bot.db.get_user_rooms(interaction.user.id, interaction.guild_id)
        
        if not rooms:
            await interaction.response.send_message(
                "У вас нет приватных комнат!",
                ephemeral=True
            )
            return

        # Создаем список для выбора комнаты
        options = []
        for room_id, voice_id, role_id, name, is_owner, is_coowner in rooms:
            options.append(
                discord.SelectOption(
                    label=name,
                    value=str(room_id),
                    description="Ваша приватная комната",
                    emoji="👑" if is_owner else "⭐" if is_coowner else "👤"
                )
            )

        class RoomSelect(discord.ui.Select):
            def __init__(self):
                super().__init__(
                    placeholder="Выберите комнату для управления",
                    min_values=1,
                    max_values=1,
                    options=options
                )

            async def callback(self, interaction: discord.Interaction):
                try:
                    room_id = int(self.values[0])
                    room_data = bot.db.get_room_data(room_id)
                    
                    if not room_data:
                        await interaction.response.send_message(
                            "Комната не найдена!",
                            ephemeral=True
                        )
                        return

                    embed = discord.Embed(
                        title="Управление комнатой",
                        description=f"Выберите действие для комнаты {room_data['name']}",
                        color=0x2b2d31
                    )
                    embed.set_thumbnail(url=interaction.user.display_avatar.url)
                    
                    view = RoomManagerView(interaction.user, room_id)
                    await interaction.response.edit_message(embed=embed, view=view)
                except Exception as e:
                    print(f"[ERROR] Error in room select callback: {str(e)}")
                    await interaction.response.send_message(
                        f"Произошла ошибка: {str(e)}",
                        ephemeral=True
                    )

        class RoomSelectView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=BUTTON_TIMEOUT)
                self.add_item(RoomSelect())

        embed = discord.Embed(
            title="Управление комнатами",
            description="Выберите комнату для управления",
            color=0x2b2d31
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        
        await interaction.response.send_message(
            embed=embed,
            view=RoomSelectView(),
            ephemeral=True
        )

    except Exception as e:
        print(f"[ERROR] Error in room command: {str(e)}")
        await interaction.response.send_message(
            f"Произошла ошибка: {str(e)}",
            ephemeral=True
        )

@bot.tree.command(
    name="marry",
    description="Сделать предложение другому игроку"
)
@app_commands.describe(
    user="Выберите игрока"
)
@app_commands.guilds(bot.GUILD)
async def marry(interaction: discord.Interaction, user: discord.User):
    try:
        # Проверяем, не пытается ли пользователь жениться на себе
        if user.id == interaction.user.id:
            await interaction.response.send_message(
                "Вы не можете жениться на самом себе!",
                ephemeral=True
            )
            return

        # Проверяем, не в браке ли уже пользователь
        proposer_marriage = bot.db.get_marriage(interaction.user.id)
        if proposer_marriage:
            await interaction.response.send_message(
                "Вы уже состоите в браке!",
                ephemeral=True
            )
            return

        # Проверяем, не в браке ли уже второй пользователь
        target_marriage = bot.db.get_marriage(user.id)
        if target_marriage:
            await interaction.response.send_message(
                "Этот пользователь уже состоит в браке!",
                ephemeral=True
            )
            return

        # Проверяем баланс
        balance = bot.db.get_balance(interaction.user.id)
        if balance["coins"] < MARRY_PRICE:
            await interaction.response.send_message(
                f"Для брака необходимо {MARRY_PRICE} {EMOJI_COINS}!",
                ephemeral=True
            )
            return

        class MarryView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=60)

            @discord.ui.button(emoji="💍", style=discord.ButtonStyle.green)
            async def accept_button(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                if button_interaction.user.id != user.id:
                    await button_interaction.response.send_message(
                        "Это не ваше предложение!",
                        ephemeral=True
                    )
                    return

                try:
                    # Списываем деньги
                    bot.db.add_currency(interaction.user.id, "coins", -MARRY_PRICE)
                    
                    # Регистрируем брак
                    bot.db.add_marriage(interaction.user.id, user.id)

                    # Выдаем роль обоим пользователям
                    love_role = button_interaction.guild.get_role(LOVE_ROLE_ID)
                    if love_role:
                        await interaction.user.add_roles(love_role)
                        await user.add_roles(love_role)

                    success_embed = discord.Embed(
                        title="💕 Новый брак!",
                        description=(
                            f"{interaction.user.mention} и {user.mention} теперь в браке!\n"
                            f"Списано: {MARRY_PRICE} {EMOJI_COINS}"
                        ),
                        color=0xFF69B4
                    )
                    await button_interaction.response.edit_message(embed=success_embed, view=None)

                    # Отправляем лог
                    await send_log(
                        bot,
                        "Новый брак",
                        f"**Пользователи:** {interaction.user.mention} и {user.mention}\n"
                        f"**Стоимость:** {MARRY_PRICE} {EMOJI_COINS}\n"
                        f"**Роль:** {love_role.mention if love_role else 'Не настроена'}",
                        log_type="love",  # Изменено с "room" на "love"
                        color=0xFF69B4
                    )

                except discord.Forbidden:
                    await button_interaction.response.send_message(
                        "У бота недостаточно прав для выдачи роли!",
                        ephemeral=True
                    )
                except Exception as e:
                    print(f"[ERROR] Error in marriage accept: {str(e)}")
                    await button_interaction.response.send_message(
                        f"Произошла ошибка: {str(e)}",
                        ephemeral=True
                    )

            @discord.ui.button(emoji="💔", style=discord.ButtonStyle.red)
            async def decline_button(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                if button_interaction.user.id != user.id:
                    await button_interaction.response.send_message(
                        "Это не ваше предложение!",
                        ephemeral=True
                    )
                    return

                decline_embed = discord.Embed(
                    title="💔 Предложение отклонено",
                    description=f"{user.mention} отклонил(а) предложение {interaction.user.mention}",
                    color=0xFF0000
                )
                await button_interaction.response.edit_message(embed=decline_embed, view=None)

        embed = discord.Embed(
            title="💝 Предложение руки и сердца",
            description=(
                f"{interaction.user.mention} делает предложение {user.mention}!\n"
                f"Стоимость: {MARRY_PRICE} {EMOJI_COINS}"
            ),
            color=0xFF69B4
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)

        await interaction.response.send_message(embed=embed, view=MarryView())

    except Exception as e:
        print(f"[ERROR] Error in marry command: {str(e)}")
        await interaction.response.send_message(
            f"Произошла ошибка: {str(e)}",
            ephemeral=True
        )

@bot.tree.command(
    name="divorce",
    description="Развестись с текущим партнером"
)
@app_commands.guilds(bot.GUILD)
async def divorce(interaction: discord.Interaction):
    try:
        # Проверяем, есть ли брак
        marriage = bot.db.get_marriage(interaction.user.id)
        if not marriage:
            await interaction.response.send_message(
                "Вы не состоите в браке!",
                ephemeral=True
            )
            return

        # Получаем ID партнера
        partner_id = marriage[1] if marriage[0] == interaction.user.id else marriage[0]
        partner = interaction.guild.get_member(partner_id)

        # Удаляем брак
        bot.db.remove_marriage(marriage[0], marriage[1])

        # Забираем роль у обоих
        love_role = interaction.guild.get_role(LOVE_ROLE_ID)
        if love_role:
            await interaction.user.remove_roles(love_role)
            if partner:
                await partner.remove_roles(love_role)

        embed = discord.Embed(
            title="💔 Развод",
            description=(
                f"{interaction.user.mention} разводится с "
                f"{partner.mention if partner else f'<@{partner_id}>'}"
            ),
            color=0xFF0000
        )
        await interaction.response.send_message(embed=embed)

        # Отправляем лог
        await send_log(
            bot,
            "Развод",
            f"**Инициатор:** {interaction.user.mention} (`{interaction.user.id}`)\n"
            f"**Партнер:** {partner.mention if partner else f'<@{partner_id}>'} (`{partner_id}`)",
            log_type="love",  # Изменено с "room" на "love"
            color=0xFF0000
        )

    except Exception as e:
        print(f"[ERROR] Error in divorce command: {str(e)}")
        await interaction.response.send_message(
            f"Произошла ошибка: {str(e)}",
            ephemeral=True
        )

@bot.tree.command(
    name="online",
    description="Показывает статистику активности пользователя"
)
@app_commands.describe(
    user="Выберите пользователя (необязательно)"
)
@app_commands.guilds(bot.GUILD)  # Добавляем этот декоратор
async def online(interaction: discord.Interaction, user: discord.User = None):
    try:
        target_user = user if user else interaction.user
        stats = bot.db.get_user_stats(target_user.id, interaction.guild.id)
        
        # Конвертируем секунды в часы, минуты и секунды
        total_seconds = stats["voice_time"]
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        embed = discord.Embed(
            title="Статистика пользователя",
            description=target_user.mention,
            color=0x2b2d31
        )
        
        embed.add_field(
            name="Время в голосовых каналах",
            value=f"```{hours:02d}:{minutes:02d}:{seconds:02d}```",
            inline=False
        )
        
        embed.add_field(
            name="Отправлено сообщений",
            value=f"```{stats['messages']}```",
            inline=False
        )
        
        embed.set_thumbnail(url=target_user.display_avatar.url)
        
        await interaction.response.send_message(embed=embed)
        
    except Exception as e:
        print(f"[ERROR] Error in online command: {str(e)}")
        await interaction.response.send_message(
            f"Произошла ошибка: {str(e)}",
            ephemeral=True
        )

@bot.tree.command(
    name="profile",
    description="Показывает профиль пользователя"
)
@app_commands.describe(
    user="Выберите пользователя (необязательно)"
)
@app_commands.guilds(bot.GUILD)
async def profile(interaction: discord.Interaction, user: discord.User = None):
    try:
        await interaction.response.defer()
        
        target_user = user if user else interaction.user
        stats = bot.db.get_user_stats(target_user.id, interaction.guild.id)
        balance = bot.db.get_balance(target_user.id)
        
        # Открываем шаблон
        template = Image.open(PROFILE_TEMPLATE_PATH).convert('RGBA')
        draw = ImageDraw.Draw(template)
        
        # Загружаем шрифт
        font = ImageFont.truetype(PROFILE_FONT_PATH, 36)
        
        # Загружаем и вставляем аватар
        avatar_url = target_user.display_avatar.replace(size=512).url
        async with aiohttp.ClientSession() as session:
            async with session.get(str(avatar_url)) as response:
                avatar_data = io.BytesIO(await response.read())
                avatar = Image.open(avatar_data).convert('RGBA')
                
                # Изменяем размер аватара
                avatar = avatar.resize((200, 200))
                
                # Создаем круглую маску для аватара
                mask = Image.new('L', (200, 200), 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.ellipse((0, 0, 200, 200), fill=255)
                
                # Вставляем аватар с новыми координатами
                avatar_x = 1136 - 100  # Центрируем аватар
                avatar_y = 152 - 100   # Центрируем аватар
                template.paste(avatar, (avatar_x, avatar_y), mask)
        
        # Имя пользователя
        name_width = draw.textlength(target_user.name, font=font)
        name_x = 1182 - (name_width / 2)  # Центрируем имя
        draw.text((name_x, 631), target_user.name, font=font, fill=(255, 255, 255))
        
        # Баланс монет
        coins_text = str(balance["coins"])
        coins_width = draw.textlength(coins_text, font=font)
        draw.text((1523 - coins_width/2, 865), coins_text, font=font, fill=(255, 255, 255))
        
        # Баланс звезд
        diamonds_text = str(balance["diamonds"])
        diamonds_width = draw.textlength(diamonds_text, font=font)
        draw.text((1552 - diamonds_width/2, 1016), diamonds_text, font=font, fill=(255, 255, 255))
        
        # Количество сообщений
        messages_text = str(stats["messages"])
        messages_width = draw.textlength(messages_text, font=font)
        draw.text((1900 - messages_width/2, 839), messages_text, font=font, fill=(255, 255, 255))
        
        # Сохраняем изображение в буфер
        buffer = io.BytesIO()
        template.save(buffer, format='PNG')
        buffer.seek(0)
        
        # Отправляем изображение
        await interaction.followup.send(
            file=discord.File(buffer, filename='profile.png')
        )
        
    except Exception as e:
        print(f"[ERROR] Error in profile command: {str(e)}")
        await interaction.followup.send(
            f"Произошла ошибка: {str(e)}",
            ephemeral=True
        )

async def main():
    async with bot:
        await bot.start(BOT_TOKEN)  # Используем токен из конфига

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен")
    except Exception as e:
        print(f"Произошла ошибка: {e}") 