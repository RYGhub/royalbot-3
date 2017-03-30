import asyncio
import datetime
import json
import random
import aiohttp
import async_timeout
import extradiscord
import markovify
import database
import royalbotconfig
import telegram

loop = asyncio.get_event_loop()
b = telegram.Bot(royalbotconfig.telegram_token)
d = extradiscord.ExtraClient(royalbotconfig.discord_token)


def currently_logged_in(thing):
    """Trova l'utente connesso all'account di Telegram che ha mandato l'update."""
    # Create a new database session
    session = database.Session()
    # Check if thing is a Telegram update
    if isinstance(thing, telegram.Update):
        user = session.query(database.User).filter_by(telegram_id=thing.message.sent_from.user_id).first()
    # Check if thing is a Discord message
    elif isinstance(thing, extradiscord.discord.Message):
        user = session.query(database.User).filter_by(discord_id=thing.author.id).first()
    # I don't know what thing is.
    else:
        raise TypeError("thing must be either a telegram.Update or a discord.Message")
    return user


async def answer(bot, thing, text):
    """Rispondi al messaggio con il canale corretto."""
    # Answer on Telegram
    if isinstance(thing, telegram.Update):
        await thing.message.reply(bot, text, parse_mode="Markdown")
    # Answer on Discord
    elif isinstance(thing, extradiscord.discord.Message):
        await bot.send_message(thing.channel, text)
    else:
        raise TypeError("thing must be either a telegram.Update or a discord.Message")


async def status_typing(bot, thing):
    """Imposta lo stato a Bot sta scrivendo..."""
    # Set typing status on Telegram
    if isinstance(thing, telegram.Update):
        await thing.message.chat.set_chat_action(bot, "typing")
    # Set typing status on Discord
    elif isinstance(thing, extradiscord.discord.Message):
        await bot.send_typing(thing.channel)
    else:
        raise TypeError("thing must be either a telegram.Update or a discord.Message")


async def display_help(bot, thing, function):
    """Display the help command of a function"""
    # Telegram bot commands start with /
    if isinstance(thing, telegram.Update):
        symbol = "/"
    # Discord bot commands start with !
    elif isinstance(thing, extradiscord.discord.Message):
        symbol = "!"
    # Unknown service
    else:
        raise TypeError("thing must be either a telegram.Update or a discord.Message")
    # Display the help message
    await answer(bot, thing, function.__doc__.format(symbol=symbol))


def find_date(thing):
    """Find the date of a message."""
    if isinstance(thing, telegram.Update):
        date = thing.message.date
    elif isinstance(thing, extradiscord.discord.Message):
        date = thing.timestamp
    else:
        raise TypeError("thing must be either a telegram.Update or a discord.Message")
    return date


async def start(bot, thing, _):
    """Saluta l'utente e visualizza lo stato account sincronizzati.

Sintassi: `{symbol}start`"""
    # Set status to typing
    await status_typing(bot, thing)
    # Find the currently logged in user
    user = currently_logged_in(thing)
    # Answer appropriately
    if user is None:
        await answer(bot, thing, f"Ciao!\n_Non hai eseguito l'accesso al RYGdb._")
    else:
        # Check the user's connected accounts
        telegram_status = "🔵" if user.telegram_id is not None else "⚪"
        discord_status = "🔵" if user.discord_id is not None else "⚪"
        await answer(bot, thing, f"Ciao!\n"
                                 f"Hai eseguito l'accesso come `{user}`.\n"
                                 f"\n"
                                 f"*Account collegati:*\n"
                                 f"{telegram_status} Telegram\n"
                                 f"{discord_status} Discord")


async def diario(bot, thing, arguments):
    """Aggiungi una frase al diario Royal Games.

Devi essere un Royal per poter eseguire questo comando.

Sintassi: `{symbol}diario <frase>`"""
    # Set status to typing
    await status_typing(bot, thing)
    # Check if the user is logged in
    if not currently_logged_in(thing):
        await answer(bot, thing, "⚠ Non hai ancora eseguito l'accesso! Usa `/sync`.")
        return
    # Check if the currently logged in user is a Royal Games member
    if not currently_logged_in(thing).royal:
        await answer(bot, thing, "⚠ Non sei autorizzato a eseguire questo comando.")
        return
    # Check the command syntax
    if len(arguments) == 0:
        await display_help(bot, thing, diario)
        return
    # Find the user
    user = currently_logged_in(thing)
    # Prepare the text
    text = " ".join(arguments).strip()
    # Add the new entry
    database.new_diario_entry(find_date(thing), text, user)
    # Answer on Telegram
    await answer(bot, thing, "✅ Aggiunto al diario!")


async def leggi(bot, thing, arguments):
    """Leggi una frase con un id specifico dal diario Royal Games.

Sintassi: {symbol}leggi <numero>"""
    # Set status to typing
    await status_typing(bot, thing)
    # Create a new database session
    session = database.Session()
    # Cast the number to an int
    try:
        n = int(arguments[0])
    except ValueError:
        await answer(bot, thing, "⚠ Il numero specificato non è valido.")
        return
    # Query the diario table for the entry with the specified id
    entry = session.query(database.Diario).filter_by(id=n).first()
    # Display the entry
    # TODO: FINISH THIS

async def leggi_telegram(bot, update, arguments):
    """Leggi una frase dal diario Royal Games.

Puoi visualizzare il diario [qui](https://royal.steffo.me/diario.htm), leggere una frase casuale scrivendo `/leggi random` o leggere una frase specifica scrivendo `/leggi <numero>`.

Sintassi: `/leggi <random | numerofrase>`"""
    # Set status to typing
    await update.message.chat.set_chat_action(bot, "typing")
    if len(arguments) == 0 or len(arguments) > 1:
        await update.message.reply(bot, "⚠ Sintassi del comando non valida.\n"
                                        "`/leggi <random | numerofrase>`", parse_mode="Markdown")
        return
    # Open the file
    file = open("diario.txt", "r", encoding="utf8")
    # Split the data in lines
    entries = file.read().split("\n")
    file.close()
    # Choose an entry
    if arguments[0] == "random":
        # either randomly...
        entry_number = random.randrange(len(entries))
    else:
        # ...or a specific one
        # TODO: check if the entry actually exists
        # TODO: check if the first argument is a number
        entry_number = int(arguments[0])
    # Split the timestamp from the text
    entry = entries[entry_number].split("|", 1)
    # Parse the timestamp
    date = datetime.datetime.fromtimestamp(int(entry[0])).isoformat()
    # Get the text
    text = entry[1]
    # Sanitize the text to prevent TelegramErrors
    text = text.replace("_", "\_").replace("*", "\*").replace("`", "\`").replace("[", "\[")
    await update.message.reply(bot, f"Frase #{entry_number} | {date}\n{text}", parse_mode="Markdown")


async def leggi_discord(bot, message, arguments):
    """Leggi una frase dal diario Royal Games.

Puoi visualizzare il diario [qui](https://royal.steffo.me/diario.htm), leggere una frase casuale scrivendo `/leggi random` o leggere una frase specifica scrivendo `/leggi <numero>`.

Sintassi: `!leggi <random | numerofrase>`"""
    if len(arguments) == 0 or len(arguments) > 1:
        await bot.send_message(message.channel, "⚠ Sintassi del comando non valida.\n`!leggi <random | numerofrase>`")
        return
    # Open the file
    file = open("diario.txt", "r", encoding="utf8")
    # Split the data in lines
    entries = file.read().split("\n")
    file.close()
    # Choose an entry
    if arguments[0] == "random":
        # either randomly...
        entry_number = random.randrange(len(entries))
    else:
        # ...or a specific one
        # TODO: check if the entry actually exists
        # TODO: check if the first argument is a number
        entry_number = int(arguments[0])
    # Split the timestamp from the text
    entry = entries[entry_number].split("|", 1)
    # Parse the timestamp
    date = datetime.datetime.fromtimestamp(int(entry[0])).isoformat()
    # Get the text
    text = entry[1]
    # Sanitize the text to prevent TelegramErrors
    text = text.replace("_", "\_").replace("*", "\*").replace("`", "\`").replace("[", "\[")
    await bot.send_message(message.channel, f"Frase #{entry_number} | {date}\n{text}")


async def markov_telegram(bot, update, arguments):
    """Genera una frase del diario utilizzando le catene di Markov.

Puoi specificare con che parole (massimo 2) deve iniziare la frase generata.
Se non vengono specificate, verrà scelta una parola a caso.

Sintassi: `/markov [inizio]`"""
    # Set status to typing
    await update.message.chat.set_chat_action(bot, "typing")
    if len(arguments) > 2:
        await update.message.reply(bot, "⚠ Sintassi del comando non valida.\n`/markov [inizio]`")
    file = open("diario.txt", "r", encoding="utf8")
    # Clean the diario
    clean_diario = str()
    # Remove the timestamps in each row
    for row in file:
        clean_diario += row.split("|", 1)[1].lower()
    # The text is split by newlines
    generator = markovify.NewlineText(clean_diario)
    file.close()
    if len(arguments) == 0:
        # Generate a sentence with a random start
        text = generator.make_sentence(tries=50)
    else:
        # Generate a sentence with a specific start
        start_with = " ".join(arguments)
        try:
            text = generator.make_sentence_with_start(start_with, tries=100)
        # No entry can start in that word.
        except KeyError:
            await update.message.reply(bot, f"⚠ Non sono state trovate corrispondenze nel diario dell'inizio che hai specificato.", parse_mode="Markdown")
            return
    if text is not None:
        # Sanitize the text to prevent TelegramErrors
        text = text.replace("_", "\_").replace("*", "\*").replace("`", "\`").replace("[", "\[")
        await update.message.reply(bot, f"*Frase generata:*\n{text}", parse_mode="Markdown")
    else:
        await update.message.reply(bot, f"⚠ Il bot non è riuscito a generare una nuova frase.\nSe è la prima volta che vedi questo errore, riprova, altrimenti prova a cambiare configurazione.")


async def help_telegram(bot, update, arguments):
    """Visualizza la descrizione di un comando.

Sintassi: `/help [comando]`"""
    # Set status to typing
    await update.message.chat.set_chat_action(bot, "typing")
    if len(arguments) == 0:
        await update.message.reply(bot, help.__doc__, parse_mode="Markdown")
    elif len(arguments) > 1:
        await update.message.reply(bot, "⚠ Sintassi del comando non valida.\n`/help [comando]`", parse_mode="Markdown")
    else:
        if arguments[0] in b.commands:
            await update.message.reply(bot, b.commands[arguments[0] + "_telegram"].__doc__, parse_mode="Markdown")
        else:
            await update.message.reply(bot, "⚠ Il comando specificato non esiste.")


async def help_discord(bot, message, arguments):
    """Visualizza la descrizione di un comando.

Sintassi: `!help [comando]`"""
    if len(arguments) == 0:
        bot.send_message(message.channel, help.__doc__)
    elif len(arguments) > 1:
        bot.send_message(message.channel, "⚠ Sintassi del comando non valida.\n`!help [comando]`")
    else:
        if arguments[0] in b.commands:
            bot.send_message(message.channel, b.commands[arguments[0] + "_discord"].__doc__)
        else:
            bot.send_message(message.channel, "⚠ Il comando specificato non esiste.")


async def discord_telegram(bot, update, arguments):
    """Manda un messaggio a #chat di Discord.

Sintassi: `/discord <messaggio>`"""
    # Set status to typing
    await update.message.chat.set_chat_action(bot, "typing")
    # Try to login
    logged_user = currently_logged_in(update)
    # Check if the user is logged in
    if not logged_user:
        await update.message.reply(bot, "⚠ Non hai ancora eseguito l'accesso! Usa `/sync`.", parse_mode="Markdown")
        return
    # Check if the currently logged in user is a Royal Games member
    if not logged_user.royal:
        await update.message.reply(bot, "⚠ Non sei autorizzato a eseguire questo comando.")
        return
    # Check the command syntax
    if len(arguments) == 0:
        await update.message.reply(bot, "⚠ Sintassi del comando non valida.\n`/discord <messaggio>`", parse_mode="Markdown")
        return
    message = " ".join(arguments)
    # Find the message sender's Discord username
    users = list(d.client.get_all_members())
    for user in users:
        if user.id == logged_user.discord_id:
            username = user.name
            break
    else:
        # Use the telegram username
        username = f"{update.message.sent_from}"
    # Parameters to send
    params = {
        "username": username,
        "content": f"{message}"
    }
    # Headers to send
    headers = {
        "Content-Type": "application/json"
    }
    # Request timeout is 10 seconds.
    with async_timeout.timeout(10):
        # Create a new session for each request.
        async with aiohttp.ClientSession() as session:
            # Send the request to the Discord webhook
            async with session.request("POST", royalbotconfig.discord_webhook, data=json.dumps(params), headers=headers) as response:
                # Check if the request was successful
                if response.status != 204:
                    # Request failed
                    # Answer on Telegram
                    await update.message.reply(bot, "⚠ L'invio del messaggio è fallito. Oops!", parse_mode="Markdown")
                    # TODO: handle Discord webhooks errors
                    raise Exception("Qualcosa è andato storto durante l'invio del messaggio a Discord.")
                # Answer on Telegram
                await update.message.reply(bot, "✅ Richiesta inviata.", parse_mode="Markdown")


async def sync_telegram(bot, update, arguments):
    """Connetti il tuo account Telegram al Database Royal Games.

Sintassi: `/sync <username> <password>`"""
    # Set status to typing
    await update.message.chat.set_chat_action(bot, "typing")
    if len(arguments) != 2:
        await update.message.reply(bot, "⚠ Sintassi del comando non valida.\n`/sync <username> <password>`", parse_mode="Markdown")
        return
    # Try to login
    session, logged_user = database.login(arguments[0], arguments[1])
    # Check if the login is successful
    if logged_user is not None:
        # Add the telegram_id to the user if it's missing
        if logged_user.telegram_id is None:
            logged_user.telegram_id = update.message.sent_from.user_id
            session.commit()
            print(f"{logged_user} ha sincronizzato l'account di Telegram.")
            await update.message.reply(bot, f"Sincronizzazione riuscita!\nSei loggato come `{logged_user}`.", parse_mode="Markdown")
        else:
            await update.message.reply(bot, "⚠ L'account è già stato sincronizzato.", parse_mode="Markdown")
    else:
        await update.message.reply(bot, "⚠ Username o password non validi.", parse_mode="Markdown")


async def sync_discord(bot, message, arguments):
    """Connetti il tuo account Discord al Database Royal Games.

Sintassi: `!sync <username> <password>`"""
    if len(arguments) != 2:
        await bot.send_message(message.channel, "⚠ Sintassi del comando non valida.\n`!sync <username> <password>`")
        return
    # Try to login
    session, logged_user = database.login(arguments[0], arguments[1])
    # Check if the login is successful
    if logged_user is not None:
        # Add the discord_id to the user if it's missing
        if logged_user.discord_id is None:
            logged_user.discord_id = int(message.author.id)
            session.commit()
            print(f"{logged_user} ha sincronizzato l'account di Discord.")
            await bot.send_message(message.channel, f"Sincronizzazione riuscita!\nSei loggato come `{logged_user}`.")
        else:
            await bot.send_message(message.channel, "⚠ L'account è già stato sincronizzato.")
    else:
        await bot.send_message(message.channel, "⚠ Username o password non validi.")


async def changepassword_telegram(bot, update, arguments):
    """Cambia la tua password del Database Royal Games.

Sintassi: `/changepassword <newpassword>`"""
    # Set status to typing
    await update.message.chat.set_chat_action(bot, "typing")
    if len(arguments) != 2:
        await update.message.reply(bot, "⚠ Sintassi del comando non valida.\n`/changepassword <oldpassword> <newpassword>`", parse_mode="Markdown")
        return
    # TODO: this can be improved, maybe?
    logged_user = currently_logged_in(update)
    # Check if the login is successful
    if logged_user is not None:
        # Change the password
        database.change_password(logged_user.username, arguments[1])
        await update.message.reply(bot, f"Il cambio password è riuscito!\n\nLa tua password è hashata nel database come_ `{logged_user.password}`_, io non la posso vedere in nessun modo!_", parse_mode="Markdown")
    else:
        await update.message.reply(bot, "⚠ Username o password non validi.", parse_mode="Markdown")


async def cv_telegram(bot, update, arguments):
    """Visualizza lo stato attuale della chat vocale Discord.

Sintassi: `/cv`"""
    # Set status to typing
    await update.message.chat.set_chat_action(bot, "typing")
    if len(arguments) != 0:
        await update.message.reply(bot, "⚠ Sintassi del comando non valida.\n`/cv`", parse_mode="Markdown")
        return
    # Wait for the Discord bot to login
    while not d.client.is_logged_in:
        await asyncio.sleep(1)
    # Find all the users in the server
    # Change this if the bot is logged in more than one server at once?
    users = list(d.client.get_all_members())
    # Find all the channels
    channels = dict()
    for user in users:
        if user.voice_channel is not None:
            if user.voice_channel.name not in channels:
                channels[user.voice_channel.name] = list()
            channels[user.voice_channel.name].append(user)
    # Create the string to send to Telegram
    to_send = str()
    for channel in channels:
        # Channel header
        to_send += f"*{channel}:*\n"
        # Users in channel
        for user in channels[channel]:
            # Online status
            if user.status.name == "online":
                # Online
                status = "🔵"
            elif user.status.name == "dnd" or (user.game is not None and user.game.type == 1):
                # Do not disturb or streaming
                status = "🔴"
            elif user.status.name == "idle":
                # Idle
                status = "⚫"
            elif user.status.name == "offline":
                # Invisible
                status = "⚪"
            else:
                # Unknown
                status = "❓"
            # Voice status
            if user.bot:
                # Music bot
                volume = "🎵"
            elif user.voice.deaf or user.voice.self_deaf:
                # Deafened
                volume = "🔇"
            elif user.voice.mute or user.voice.self_mute:
                # Muted
                volume = "🔈"
            else:
                # Speaking
                volume = "🔊"
            # Game, is formatted
            if user.game is not None:
                # Playing
                if user.game.type == 0:
                    # Game name
                    game = f"- *{user.game.name}*"
                # Streaming
                elif user.game.type == 1:
                    # Stream name and url
                    game = f"- [{user.game.name}]({user.game.url})"
            else:
                game = ""
            # Nickname if available, otherwise use the username
            if user.nick is not None:
                name = user.nick
            else:
                name = user.name
            # Add the user
            to_send += f"{volume} {status} {name} {game}\n"
        # Channel footer
        to_send += "\n"
    await update.message.reply(bot, to_send, parse_mode="Markdown", disable_web_page_preview=1)


async def roll_telegram(bot, update, arguments):
    """Lancia un dado a N facce.

Sintassi: `/roll <max>`"""
    # Set status to typing
    await update.message.chat.set_chat_action(bot, "typing")
    # Check the command syntax
    if len(arguments) != 1:
        await update.message.reply(bot, "⚠ Sintassi del comando non valida.\n`/roll <max>`",
                                   parse_mode="Markdown")
        return
    # Roll the dice!
    await update.message.reply(bot, f"*Numero generato:* {random.randrange(0, int(arguments[0])) + 1}", parse_mode="Markdown")


async def roll_discord(bot, message, arguments):
    """Lancia un dado a N facce.

Sintassi: `!roll <max>`"""
    # Check the command syntax
    if len(arguments) != 1:
        await bot.send_message(message.channel, "⚠ Sintassi del comando non valida.\n`!roll <max>`")
        return
    # Roll the dice!
    await bot.send_message(message.channel, f"*Numero generato:* {random.randrange(0, int(arguments[0])) + 1}")


async def register_telegram(bot, update, arguments):
    """Registrati al database Royal Games!

Sintassi: `/register <username> <password>`"""
    # One account per user only!
    if currently_logged_in(update) is not None:
        await update.message.reply(bot, "⚠ Sei già registrato!")
        return
    # Check if the username is printable
    if not arguments[0].isprintable():
        await update.message.reply(bot, "⚠ Username non valido.")
        return
    # Try to create a new user
    try:
        database.create_user(arguments[0], arguments[1], False)
    except database.sqlalchemy.exc.DBAPIError:
        await update.message.reply(bot, "⚠ Qualcosa è andato storto nella creazione dell'utente. Per altre info, guarda i log del bot.")
        raise
    else:
        session, logged_user = database.login(arguments[0], arguments[1])
        logged_user.telegram_id = update.message.sent_from.user_id
        session.commit()
        print(f"{logged_user} ha sincronizzato l'account di Telegram.")
        await update.message.reply(bot, f"Sincronizzazione riuscita!\nSei loggato come `{logged_user}`.", parse_mode="Markdown")

async def toggleroyal_telegram(bot, update, arguments):
    """Inverti lo stato di Royal di un utente.
    
Devi essere un Royal per poter eseguire questo comando.

Sintassi: `/toggleroyal <username>`"""
    # Check if the user is logged in
    if not currently_logged_in(update):
        await update.message.reply(bot, "⚠ Non hai ancora eseguito l'accesso! Usa `/sync`.", parse_mode="Markdown")
        return
    # Check if the currently logged in user is a Royal Games member
    if not currently_logged_in(update).royal:
        await update.message.reply(bot, "⚠ Non sei autorizzato a eseguire questo comando.")
        return
    # Check the command syntax
    if len(arguments) != 1:
        await update.message.reply(bot, "⚠ Sintassi del comando non valida.\n`/toggleroyal <username>`", parse_mode="Markdown")
        return
    # Find the specified user
    session, user = database.find_user(arguments[0])
    # Check if the user exists
    if user is None:
        await update.message.reply(bot, "⚠ L'utente specificato non esiste.")
        return
    # Toggle his Royal status
    user.royal = not user.royal
    # Save the change
    session.commit()
    # Answer on Telegram
    if user.royal:
        await update.message.reply(bot, f"✅ L'utente `{user.username}` ora è un Royal.", parse_mode="Markdown")
    else:
        await update.message.reply(bot, f"✅ L'utente `{user.username}` non è più un Royal.", parse_mode="Markdown")

if __name__ == "__main__":
    # Init universal bot commands
    b.commands["start"] = start
    d.commands["start"] = start
    b.commands["diario"] = diario
    d.commands["diario"] = diario
    # Init Telegram bot commands
    b.commands["leggi"] = leggi_telegram
    b.commands["discord"] = discord_telegram
    b.commands["sync"] = sync_telegram
    b.commands["changepassword"] = changepassword_telegram
    b.commands["help"] = help_telegram
    b.commands["markov"] = markov_telegram
    b.commands["cv"] = cv_telegram
    b.commands["roll"] = roll_telegram
    b.commands["register"] = register_telegram
    b.commands["toggleroyal"] = toggleroyal_telegram
    # Init Discord bot commands
    d.commands["sync"] = sync_discord
    d.commands["roll"] = roll_discord
    d.commands["help"] = help_discord
    d.commands["leggi"] = leggi_discord
    # Init Telegram bot
    loop.create_task(b.run())
    print("Telegram bot start scheduled!")
    # Init Discord bot
    loop.create_task(d.run())
    print("Discord bot start scheduled!")
    # Run everything!
    loop.run_forever()