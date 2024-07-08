import aiohttp
import asyncio
from twitchio.ext import commands
from twitchio import Message
from collections import defaultdict, deque
from datetime import datetime, timedelta
import logging
import re
import enchant
import requests

logging.basicConfig(level=logging.INFO)

# Сохраняем сообщения пользователей
user_messages = defaultdict(lambda: deque(maxlen=100))
russian_chars = set('абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ')
# Перевод раскладки
def translate_layout(text):
    layout = {
        'q': 'й', 'w': 'ц', 'e': 'у', 'r': 'к', 't': 'е', 'y': 'н', 'u': 'г', 'i': 'ш', 'o': 'щ', 'p': 'з', '[': 'х', ']': 'ъ',
        'a': 'ф', 's': 'ы', 'd': 'в', 'f': 'а', 'g': 'п', 'h': 'р', 'j': 'о', 'k': 'л', 'l': 'д', ';': 'ж', "'": 'э',
        'z': 'я', 'x': 'ч', 'c': 'с', 'v': 'м', 'b': 'и', 'n': 'т', 'm': 'ь', ',': 'б', '.': 'ю', '/': '.',
        'Q': 'Й', 'W': 'Ц', 'E': 'У', 'R': 'К', 'T': 'Е', 'Y': 'Н', 'U': 'Г', 'I': 'Ш', 'O': 'Щ', 'P': 'З', '{': 'Х', '}': 'Ъ',
        'A': 'Ф', 'S': 'Ы', 'D': 'В', 'F': 'А', 'G': 'П', 'H': 'Р', 'J': 'О', 'K': 'Л', 'L': 'Д', ':': 'Ж', '"': 'Э',
        'Z': 'Я', 'X': 'Ч', 'C': 'С', 'V': 'М', 'B': 'И', 'N': 'Т', 'M': 'Ь', '<': 'Б', '>': 'Ю', '?': ',',
        '@': '"', '#': '№', '$': ';', '^': ':', '&': '?',
        # Добавляем обратный перевод
        'й': 'q', 'ц': 'w', 'у': 'e', 'к': 'r', 'е': 't', 'н': 'y', 'г': 'u', 'ш': 'i', 'щ': 'o', 'з': 'p', 'х': '[', 'ъ': ']',
        'ф': 'a', 'ы': 's', 'в': 'd', 'а': 'f', 'п': 'g', 'р': 'h', 'о': 'j', 'л': 'k', 'д': 'l', 'ж': ';', 'э': "'",
        'я': 'z', 'ч': 'x', 'с': 'c', 'м': 'v', 'и': 'b', 'т': 'n', 'ь': 'm',
        'Й': 'Q', 'Ц': 'W', 'У': 'E', 'К': 'R', 'Е': 'T', 'Н': 'Y', 'Г': 'U', 'Ш': 'I', 'Щ': 'O', 'З': 'P', 'Х': '{', 'Ъ': '}',
        'Ф': 'A', 'Ы': 'S', 'В': 'D', 'А': 'F', 'П': 'G', 'Р': 'H', 'О': 'J', 'Л': 'K', 'Д': 'L', 'Ж': ':', 'Э': '"',
        'Я': 'Z', 'Ч': 'X', 'С': 'C', 'М': 'V', 'И': 'B', 'Т': 'N', 'Ь': 'M'
    }
    return ''.join([layout.get(i, i) for i in text])

class Bot(commands.Bot):

    def __init__(self):
        super().__init__(token='sjwr9h9p8a6njfp1nmy8vng6nstkpf', prefix='!', initial_channels=['mjkey','abadonblack','ztrion','aylot_'])
        self.slang_words_dict = defaultdict(lambda: True)

    async def _get_7tv_emotes(self, url):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    emotes = (await response.json()).get('emote_set', {}).get('emotes', [])
                    return [emote.get('name') for emote in emotes]
                else:
                    return None

    async def event_ready(self):
        logging.info(f'Ready | {self.nick}')

    async def event_message(self, message: Message):
        if message.author is not None and message.author.name != self.nick and not message.content.startswith('!эльф'):
            user_messages[message.author.name.lower()].append((message.content, datetime.now()))
        if message.author is not None and message.author.name != self.nick and message.author.name != 'moobot' and not message.content.startswith('@') and not message.content.startswith('http') and not message.content.startswith('!') and not message.tags.get('emote-only') and not any(char in russian_chars for char in message.content):
            logging.info(f'Message from {message.author.name}: {message.content}')
            

            # Проверка на русский язык
            if any(char.isalpha() and char.isascii() for char in message.content):
                words = message.content.split()
                # Проверка на английские слова или сленг
                if sum(1 for word in words if is_english_or_slang(word)) / len(words) <= 0.60:
                    
                    # Получаем список смайликов из сообщения
                    emotes_str = message.tags.get('emotes', '')
                    # Создаем копию сообщения для перевода
                    translated_message = message.content[:]
                    # Разбиваем строку смайликов на отдельные смайлики
                    for emote in emotes_str.split('/'):
                        # Извлекаем диапазоны смайлика
                        ranges = emote.split(':')[1:] if len(emote.split(':')) > 1 else []
                        # Заменяем символы смайлика на пустую строку
                        for range_str in ranges:
                            range_values = list(map(int, re.findall(r'\d+', range_str)))
                            start, end = range_values[0], range_values[-1] if range_values else (0, 0)

                            translated_message = (
                                translated_message[:start] + ' ' * (end - start + 1) + translated_message[end + 1:]
                            )
                    # Переводим раскладку
                            
                    translated_message = translate_layout(translated_message)
                    await message.channel.send(f'Был обнаружен эльф @{message.author.name} PopNemo -> {translated_message}')

        if message.author is not None:
            await self.handle_commands(message)
        else:
            pass

    @commands.command(name='эльф')
    async def my_command(self, ctx, nick: str = None, num_messages: int = 1):
        if nick is None:
            nick = ctx.author.name

        nick = nick.lstrip('@').lower()

        logging.info(f'Received !эльф command from {ctx.author.name} with nick: {nick}, num_messages: {num_messages}')

        messages = list(user_messages.get(nick, []))
        if not messages:
            logging.info(f'No messages found for user {nick}.')
            await ctx.send(f'Сообщение от пользователя {nick} не найдено или устарело (5 мин).')
            return

        translated_messages = []
        for i, (message, timestamp) in enumerate(messages[-num_messages:], start=1):
            if datetime.now() - timestamp < timedelta(minutes=5):
                message_content_without_mentions = re.sub(r'@(\w+)', '', message)
                translated_message = translate_layout(message_content_without_mentions)
                logging.info(f'Translated message {i}: {translated_message}')
                if num_messages > 1:
                    translated_messages.append(f'{i}. {translated_message}')
                else:
                    translated_messages.append(translated_message)
            else:
                logging.info(f'Message {i} from user {nick} is outdated (more than 5 minutes).')
                await ctx.send(f'Сообщение {i} от пользователя {nick} устарело (5 мин).')

        if translated_messages:
            full_message = " ".join(translated_messages)
            logging.info(f"Sending response to {ctx.author.name}: {full_message}")
            await ctx.send(f"Эльф {nick} PopNemo -> " + full_message)



# Словарь английского языка
english_dict = enchant.Dict("en_US")

def get_7tv_emotes(url):
    response = requests.get(url)
    if response.status_code == 200:
        emotes = response.json().get('emote_set', {}).get('emotes', [])
        return [emote.get('name') for emote in emotes]
    else:
        return None

slang_words = ['u', 'r', 'thx', 'plz', 'Kappa', 'PogChamp', 'LUL', 'OMEGALUL', 'FeelsBadMan', 'FeelsGoodMan',
            '4Head', 'BibleThump', 'BabyRage', 'DansGame', 'Kreygasm', 'Keepo', 'NotLikeThis', 'TriHard', 
            'WutFace', 'CoolStoryBob', 'PepeHands', 'Pepega', 'monkaS', 'monkaW', 'PepeLaugh', 'EZ', 'POGGERS', 
            'HYPERS', 'WutFace', 'SourPls', 'VoHiYo', 'ResidentSleeper', 'BlessRNG', 'SwiftRage', 'Jebaited', 
            'LULW', 'PopNemo', 'KonCha', 'peepoHappy', 'peepoSad', 'peepoWTF', 'peepoGiggles', 'peepoClap', 'peepoThink', 'peepoRiot',
            # Добавляем стандартные смайлики Twitch
            'OpieOP', 'ResidentSleeper', 'strawbeWavy', 'JKanStyle', 'KappaRoss', 'KappaClaus', 'OhMyDog', 
            'OSFrog', 'CoolCat', 'DendiFace', 'NotATK', 'ANELE', 'AsianGlow', 'BibleThump', 'BrokeBack', 
            'DansGame', 'EleGiggle', 'FailFish', 'FrankerZ', 'Kappa', 'KappaPride', 'KappaWealth', 'Keepo', 
            'Kreygasm', 'MingLee', 'PJSalt', 'SMOrc', 'SSSsss', 'SwiftRage', 'TheThing', 'TriHard', 'VoHiYo', 
            'WutFace', 'seemsgood', 'imGlitch','EBLAN','elfi','COCATb','sus',
            # Добавляем стандартные смайлики 7tv
            'LULW', 'OMEGALUL', 'PepeLaugh', 'KEKW', 'monkaW', '5Head', 'PogU', 'Pepega', 'Sadge', 'WeirdChamp', 
            'POGGERS', 'AYAYA', 'peepoHappy', 'peepoSad', 'YEP', 'NOPE', 'monkaHmm', 'monkaS', 'FeelsBadMan', 
            'FeelsGoodMan', 'PepeHands', 'WideHardo', 'HYPERS', 'EZ', 'PagChomp', 'PauseChamp', 'PogChamp', 
            'Pog', 'PepeDS', 'PepeD', 'PepeDM','AlienDance',
            # Добавляем стандартные смайлики BetterTV
            'PepeHands', 'monkaS', 'OMEGALUL', 'POGGERS', 'Pepega', 'PepePls', 'AYAYA', 'FeelsBadMan', 
            'FeelsGoodMan', 'KEKW', 'LULW', 'monkaW', 'Pog', 'PogU', 'Sadge', 'WeirdChamp', 'YEP', '5Head', 
            'Clap', 'EZ', 'HYPERS', 'PagChomp', 'PauseChamp', 'PepeD', 'PepeDS', 'PepeG', 'PepeJAM', 'PepeLaugh', 
            'PogChamp', 'PogO', 'WideHardo', 'WutFace', 'catJAM', 'gachiGASM', 'haHAA', 'peepoHappy', 'peepoSad',
            # Sleng
            'Qq','qq','bb','BB','omg','wtf','ztrion', 'fack','Grimes']



urls = [
    "https://7tv.io/v3/users/TWITCH/180238325",
    "https://7tv.io/v3/users/TWITCH/135635544",
    "https://7tv.io/v3/users/TWITCH/129543225",
    "https://7tv.io/v3/users/TWITCH/507362070"
]

for url in urls:
    emotes = get_7tv_emotes(url)
    if emotes is not None:
        slang_words.extend(emotes)


# Проверка на английское слово или сленг
def clean_word(word):
    return re.sub(r'\W+', '', word)

# Проверка на английское слово или сленг
def is_english_or_slang(word):
    cleaned_word = clean_word(word)
    if cleaned_word:  # Проверка на пустую строку
        return english_dict.check(cleaned_word) or cleaned_word in slang_words
    else:
        return False

bot = Bot()
bot.run()
