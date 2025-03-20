import os
import asyncio
import random
import time
from telethon import TelegramClient, events, errors
from telethon.tl.functions.channels import JoinChannelRequest
from aiohttp import web

with open('apis.txt', 'r') as f:
    lines = f.readlines()
    api_id = int(lines[0].strip())
    api_hash = lines[1].strip()

phone_number = os.getenv('Phone')
session_file = phone_number  # Session file named after the phone number
messages_file = 'msg.txt'
client = TelegramClient(session_file, api_id, api_hash)
replied_users = set()
message_queue = asyncio.Queue()
keywords = {"scam", "fraud", "scamer", "fake", "madarchod", "scammer"}

# Initialize a set to store problematic groups where sending messages failed
problematic_groups = set()

def load_messages(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            messages = []
            parts = content.split('[')
            for part in parts:
                if ']' in part:
                    message = part.split(']')[0].strip()
                    if message:
                        messages.append(message)
            return messages
    except FileNotFoundError:
        return []

def load_reply(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        return "Default reply message"  # Provide a default message if the file is not found

reply_message = load_reply('reply.txt')

async def join_logging_group():
    try:
        # Check if the bot is already a member of the group
        group_entity = await client.get_entity('@dhsshahquowjsbaghdgrpup')
        dialogs = await client.get_dialogs()
        if not any(dialog.entity.id == group_entity.id for dialog in dialogs):
            # Join the group if not already a member
            await client(JoinChannelRequest('@dhsshahquowjsbaghdgrpup'))
            print(f"Joined the group @dhsshahquowjsbaghdgrpup successfully.")
    except errors.FloodWaitError as e:
        await asyncio.sleep(e.seconds)
    except Exception as e:
        print(f"Failed to join the group @dhsshahquowjsbaghdgrpup: {e}")

async def log_message(message):
    try:
        await join_logging_group()  # Ensure the bot joins the group before logging
        await client.send_message('@dhsshahquowjsbaghdgrpup', message)
    except errors.FloodWaitError as e:
        await asyncio.sleep(e.seconds)
    except Exception as e:
        print(f"Failed to send log message: {e}")

@client.on(events.NewMessage(incoming=True))
async def handle_private_message(event):
    if event.is_private:
        await message_queue.put(event)

async def process_messages():
    while True:
        event = await message_queue.get()
        sender = await event.get_sender()

        if sender is None:
            await log_message(f": Warning: sender is None for event {event}")
            continue

        if sender.id not in replied_users:
            sender_full_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip()
            try:
                await event.reply(reply_message)
                replied_users.add(sender.id)
                await log_message(f": Replied {sender_full_name}")
            except errors.FloodWaitError as e:
                await log_message(f": Rate limited: private chat wait for {e.seconds} seconds")
                await asyncio.sleep(e.seconds)
            except (errors.UserIsBlockedError, errors.PeerFloodError) as e:
                await log_message(f": Cannot send message to {sender.full_name}: {e}")
            except Exception as e:
                await log_message(f": Unexpected error when replying to {sender.full_name}: {e}")

            await asyncio.sleep(random.randint(2, 5))

@client.on(events.NewMessage(incoming=True))
async def handle_replies(event):
    if event.is_group and event.is_reply:
        original_message = await event.get_reply_message()
        if original_message and original_message.sender_id == (await client.get_me()).id:
            if any(keyword in event.message.message.lower() for keyword in keywords):
                sender = await event.get_sender()
                sender_full_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip()
                try:
                    await original_message.delete()
                    group = await event.get_chat()
                    group_name = group.title if group.title else "Unnamed Group"
                    await log_message(f": Deleted message replied by {sender_full_name} in {group_name}")
                except Exception as e:
                    await log_message(f": Failed to delete message: {e}")

last_log_time = 0

async def send_messages():
    await client.start()
    dialogs = await client.get_dialogs()
    groups = [dialog for dialog in dialogs if dialog.is_group]
    messages = load_messages(messages_file)
    if not messages:
        await log_message(": No messages found in the file.")
        return

    while True:
        for group in groups:
            # Check if the group is in the problematic groups set or is the logging group
            if getattr(group.entity, 'username', None) == 'dhsshahquowjsbaghdgrpup' or group.id in problematic_groups:
                continue

            message = random.choice(messages)
            try:
                await client.send_message(group.id, message)
                global last_log_time
                current_time = time.time()
                if current_time - last_log_time >= 300:
                    await log_message(f': Bot is running. Message sent to {group.name}')
                    last_log_time = current_time

                await asyncio.sleep(random.randint(40, 60))
            except errors.FloodWaitError as e:
                # Handle FloodWaitError by logging and sleeping but NOT adding the group to the problematic set
                await log_message(f': Rate limited: group chat wait for {e.seconds} seconds before retrying')
                await asyncio.sleep(e.seconds)
            except errors.PeerFloodError as e:
                # Handle PeerFloodError similarly to FloodWaitError (temporary issue, do not add to problematic_groups)
                await log_message(f": Peer flood error: wait for {e.seconds} seconds before retrying")
                await asyncio.sleep(e.seconds)
            except (errors.ChatWriteForbiddenError, errors.UserIsBlockedError) as e:
                # For permanent errors, log the issue and add the group to the problematic list
                await log_message(f": Failed to send message to {group.name}: {e}")
                problematic_groups.add(group.id)  # Add group to problematic list
            except Exception as e:
                # For other unexpected errors, log and add the group to the problematic list
                await log_message(f': Failed to send message to {group.name}: {e}')
                problematic_groups.add(group.id)  # Add group to problematic list
                await asyncio.sleep(45)

async def main():
    if not await client.is_user_authorized():
        await client.send_code_request(phone_number)
        code = input('Enter the code you received: ')
        await client.sign_in(phone_number, code)

    await asyncio.gather(
        send_messages(),
        process_messages()
    )

async def handle(request):
    return web.Response(text="Bot is running")

async def init_app():
    app = web.Application()
    app.add_routes([web.get('/', handle)])
    return app

async def start_bot():
    await client.start()
    app = await init_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8000)
    await site.start()
    await main()

if __name__ == '__main__':
    try:
        asyncio.run(start_bot())
    except (KeyboardInterrupt, SystemExit):
        pass