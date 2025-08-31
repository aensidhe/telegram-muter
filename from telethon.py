from telethon.sync import TelegramClient
from telethon.tl.functions.account import UpdateNotifySettingsRequest
from telethon.tl.types import InputPeerNotifySettings, InputPeerChannel
from datetime import datetime, timedelta

# Replace these with your own values
api_id = 'YOUR_API_ID'
api_hash = 'YOUR_API_HASH'
phone_number = 'YOUR_PHONE_NUMBER'

# Connect to the Telegram API
client = TelegramClient('session_name', api_id, api_hash)
client.connect()

# Ensure you're authorized
if not client.is_user_authorized():
    client.send_code_request(phone_number)
    client.sign_in(phone_number, input('Enter the code: '))

# Get all dialogs (chats/groups)
dialogs = client.get_dialogs()

# Calculate the mute_until time (10:00 AM next day)
now = datetime.now()
mute_until = now.replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=1)

# Iterate through dialogs and mute unmuted groups
for dialog in dialogs:
    if hasattr(dialog.entity, 'broadcast') and not dialog.entity.broadcast:
        # Check if the group is muted
        notify_settings = dialog.notify_settings
        if not notify_settings or not notify_settings.mute_until:
            # Mute the group until 10:00 AM next day
            settings = InputPeerNotifySettings(
                mute_until=mute_until,
                show_previews=False
            )
            client(UpdateNotifySettingsRequest(
                peer=InputPeerChannel(dialog.entity.id, dialog.entity.access_hash),
                settings=settings
            ))
            print(f"Muted group: {dialog.name}")

# Disconnect from the Telegram API
client.disconnect()
