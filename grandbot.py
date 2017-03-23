import asyncio
import datetime
import json
import random
import aiohttp
import async_timeout
import extra_discord
import markovify
import database
import royalbotconfig
import telegram

loop = asyncio.get_event_loop()
b = telegram.Bot(royalbotconfig.telegram_token)
d = extra_discord.ExtraClient(royalbotconfig.discord_token)


def currently_logged_in(update):
    """Trova l'utente connesso all'account di Telegram che ha mandato l'update."""
    session = database.Session()
    user = session.query(database.User).filter_by(telegram_id=update.message.sent_from.user_id).first()
    return user


async def start(bot, update, arguments):
    user = currently_logged_in(update)
    if user is None:
        await update.message.reply(bot, f"Ciao!\n_Non hai eseguito l'accesso al RYGdb._", parse_mode="Markdown")
    else:
        telegram_status = "🔵" if user.telegram_id is not None else "⚪"
        discord_status = "🔵" if user.discord_id is not None else "⚪"
        await update.message.reply(bot, f"Ciao!\nHai eseguito l'accesso come `{user}`.\nAttualmente hai {user.coins} ℝ.\n\n*Account collegati:*\n{telegram_status} Telegram\n{discord_status} Discord", parse_mode="Markdown")


async def diario(bot, update, arguments):
    """Aggiungi una frase al diario Royal Games.

Devi essere un Royal per poter eseguire questo comando.

Sintassi: `/diario <frase>`"""
    # Check if the user is logged in
    if not currently_logged_in(update):
        await update.message.reply(bot, "⚠ Non hai ancora eseguito l'accesso! Usa `/sync`.", parse_mode="Markdown")
        return
    # Check if the currently logged in user is a Royal Games member
    if not currently_logged_in(update).royal:
        await update.message.reply(bot, "⚠ Non sei autorizzato a eseguire questo comando.")
        return
    # Check the command syntax
    if len(arguments) == 0:
        await update.message.reply(bot, "⚠ Sintassi del comando non valida.\n`/diario <random | markov | numerofrase>`", parse_mode="Markdown")
        return
    # Check for non-ASCII characters
    entry = " ".join(arguments)
    if not entry.isprintable():
        await update.message.reply(bot, "⚠ La frase che stai provando ad aggiungere contiene caratteri non ASCII, quindi non è stata aggiunta.\nToglili e riprova!")
        return
    # Remove endlines
    entry = entry.replace("\n", " ")
    # TODO: check if a end-of-file character can be sent on Telegram
    # Generate a timestamp
    time = update.message.date.timestamp()
    # Write on the diario file
    file = open("diario.txt", "a", encoding="utf8")
    file.write(f"{int(time)}|{entry}\n")
    file.close()
    del file
    # Answer on Telegram
    await update.message.reply(bot, "✅ Aggiunto al diario!")


async def leggi(bot, update, arguments):
    """Leggi una frase dal diario Royal Games.

Puoi visualizzare il diario [qui](https://royal.steffo.me/diario.htm), leggere una frase casuale scrivendo `/leggi random` o leggere una frase specifica scrivendo `/leggi <numero>`.

Sintassi: `/leggi <random | numerofrase>`"""
    if len(arguments) == 0 or len(arguments) > 1:
        await update.message.reply(bot, "⚠ Sintassi del comando non valida.\n`/leggi <random | numerofrase>`", parse_mode="Markdown")
        return
    # Open the file
    file = open("diario.txt", "r")
    # Split the data in lines
    entries = file.read().split("\n")
    file.close()
    # Choose an entry
    if arguments[0] == "random":
        # either randomly...
        entry_number = random.randrange(len(entries))
    else:
        # ...or a specific one
        entry_number = arguments[0]
    # Split the timestamp from the text
    entry = entries[entry_number].split("|", 1)
    # Parse the timestamp
    date = datetime.datetime.fromtimestamp(entry[0]).isoformat()
    # Get the text
    text = entry[1]
    # Sanitize the text to prevent TelegramErrors
    text = text.replace("_", "\_").replace("*", "\*").replace("`", "\`").replace("[", "\[")
    await update.message.reply(bot, f"Frase #{entry_number} | {date}\n{text}", parse_mode="Markdown")


async def markov(bot, update, arguments):
    """Genera una frase del diario utilizzando le catene di Markov.

Puoi specificare con che parole (massimo 2) deve iniziare la frase generata.
Se non vengono specificate, verrà scelta una parola a caso.

Sintassi: `/markov [inizio]`"""
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


async def help_cmd(bot, update, arguments):
    """Visualizza la descrizione di un comando.

Sintassi: `/help [comando]`"""
    if len(arguments) == 0:
        await update.message.reply(bot, help.__doc__, parse_mode="Markdown")
    elif len(arguments) > 1:
        await update.message.reply(bot, "⚠ Sintassi del comando non valida.\n`/help [comando]`", parse_mode="Markdown")
    else:
        if arguments[0] in b.commands:
            await update.message.reply(bot, b.commands[arguments[0]].__doc__, parse_mode="Markdown")
        else:
            await update.message.reply(bot, "⚠ Il comando specificato non esiste.")


async def discord(bot, update, arguments):
    """Manda un messaggio a #chat di Discord.

Sintassi: `/discord <messaggio>`"""
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
            logged_user.coins += 1
            session.commit()
            print(f"{logged_user} ha sincronizzato l'account di Telegram.")
            await update.message.reply(bot, f"Sincronizzazione riuscita!\nSei loggato come `{logged_user}`.\nHai guadagnato 1 ℝ.", parse_mode="Markdown")
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
            logged_user.coins += 1
            session.commit()
            print(f"{logged_user} ha sincronizzato l'account di Discord.")
            await bot.send_message(message.channel, f"Sincronizzazione riuscita!\nSei loggato come `{logged_user}`.\nHai guadagnato 1 ℝ.")
        else:
            await bot.send_message(message.channel, "⚠ L'account è già stato sincronizzato.")
    else:
        await bot.send_message(message.channel, "⚠ Username o password non validi.")


async def changepassword(bot, update, arguments):
    """Cambia la tua password del Database Royal Games.

Sintassi: `/changepassword <newpassword>`"""
    if len(arguments) != 2:
        await update.message.reply(bot, "⚠ Sintassi del comando non valida.\n`/changepassword <oldpassword> <newpassword>`", parse_mode="Markdown")
        return
    # TODO: this can be improved, maybe?
    logged_user = currently_logged_in(update)
    # Check if the login is successful
    if logged_user is not None:
        # Change the password
        database.change_password(logged_user.username, arguments[1])
        await update.message.reply(bot, f"Il cambio password è riuscito!\n\n_Info per smanettoni: la tua password è hashata nel database come_ `{logged_user.password}`.", parse_mode="Markdown")
    else:
        await update.message.reply(bot, "⚠ Username o password non validi.", parse_mode="Markdown")


async def cv(bot, update, arguments):
    """Visualizza lo stato attuale della chat vocale Discord.

Sintassi: `/cv`"""
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


async def buy(bot, update, arguments):
    """Compra nuovi ℝ!

Sintassi: /buy"""
    # TODO: finiscimi
    app = random.sample(["https://play.google.com/store/apps/details?id=com.mp.HorseRide",
                         "https://play.google.com/store/apps/details?id=com.kick.ultimate.rooftop.police.chase",
                         "https://play.google.com/store/apps/details?id=com.do_apps.catalog_65",
                         "https://play.google.com/store/apps/details?id=com.pikpok.rua2",
                         "http://steffo.me/barbaxmas.htm"], 1)[0]
    await update.message.reply(bot, f"*Scegli un'operazione:*\n"
                                    f"[Acquista 1 ℝ](https://royal.steffo.me/store/1) per € 0.99!\n"
                                    f"[Acquista 3 ℝ](https://royal.steffo.me/store/3) per € 1.99 (Risparmi € 0.98!)!\n"
                                    f"[Acquista 6 ℝ](https://royal.steffo.me/store/6) per € 2.49 (Risparmi € 3.45!)!\n"
                                    f"[Acquista 25 ℝ](https://royal.steffo.me/store/25) per € 4.99 (Risparmi € 19.76!)\n"
                                    f"[Acquista 69 ℝ](https://royal.steffo.me/store/69) per € 6.66 (Risparmi € 61.65!)\n"
                                    f"[OFFERTA FORTUNATA SOLO PER TE! Acquista 777 ℝ](https://royal.steffo.me/store/777) per € 17.77!\n"
                                    f"[Ottieni 322 ℝ](https://dotabuff.com/betting) scommettendo per la prima volta sul sito dei nostri sponsor!\n"
                                    f"[Ottieni 104 ℝ](https://royal.steffo.me/store/video) guardando un video sponsorizzato!\n"
                                    f"**Ottieni 30 ℝ** per ogni amico che inviti alla Royal Games!\n"
                                    f"[Ottieni 1337 ℝ]({app}) installando l'app dei nostri partner!\n"
                                    f"**Ottieni 1 ℝ** al giorno aggiungendo `steffo.me` alla fine del tuo username di Steam!\n\n"
                                    f"NOTA LEGALE: @Steffo non si assume responsabilità per il contenuto delle app sponsorizzate. Fate attenzione!")


if __name__ == "__main__":
    # Init Telegram bot commands
    b.commands["start"] = start
    b.commands["leggi"] = leggi
    b.commands["diario"] = diario
    b.commands["discord"] = discord
    b.commands["sync"] = sync_telegram
    b.commands["changepassword"] = changepassword
    b.commands["help"] = help_cmd
    b.commands["markov"] = markov
    b.commands["cv"] = cv
    # Init Discord bot commands
    d.commands["sync"] = sync_discord
    # Init Telegram bot
    loop.create_task(b.run())
    print("Telegram bot start scheduled!")
    # Init Discord bot
    loop.create_task(d.run())
    print("Discord bot start scheduled!")
    # Run everything!
    loop.run_forever()