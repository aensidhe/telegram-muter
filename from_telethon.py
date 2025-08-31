import asyncio
from datetime import datetime, timedelta
from getpass import getpass
from telethon import TelegramClient
from telethon.errors.rpcerrorlist import SessionPasswordNeededError
from telethon.tl.functions.account import UpdateNotifySettingsRequest
from telethon.tl.types import InputPeerNotifySettings, InputPeerChannel

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')
    api_id: int = Field(alias="API_ID")
    api_hash: str = Field(alias="API_HASH")
    phone_number: str = Field(alias="PHONE_NUMBER")

settings = Settings() # type: ignore

async def main():
    # Connect to the Telegram API
    client = TelegramClient('ru.aensidhe.console_groups_muter', settings.api_id, settings.api_hash)
    await client.connect()

    # Ensure you're authorized
    if not await client.is_user_authorized():
        await client.send_code_request(settings.phone_number)
        try:
            await client.sign_in(settings.phone_number, input('Enter the code: '))
        except SessionPasswordNeededError:
            await client.sign_in(settings.phone_number, password=getpass('Enter 2FA password: '))

    # Calculate the mute_until time (10:00 AM next day)
    now = datetime.now()
    mute_until = now.replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=1)

    # Fetch all dialogs with pagination
    all_dialogs = await client.get_dialogs(limit=None) # type: ignore

    # Iterate through all dialogs and mute unmuted groups
    for dialog in all_dialogs: # type: ignore
        if hasattr(dialog.entity, 'broadcast') and not dialog.entity.broadcast: # type: ignore
            print(f'Got chat `{dialog.name}`') # type: ignore
            # Check if the group is muted
            notify_settings = dialog.notify_settings if hasattr(dialog, 'notify_settings') else None # type: ignore
            if not notify_settings or not notify_settings.mute_until: # type: ignore
                # Mute the group until 10:00 AM next day
                mute_settings = InputPeerNotifySettings(
                    mute_until=mute_until,
                    show_previews=False
                )
                await client(UpdateNotifySettingsRequest(
                    peer=InputPeerChannel(dialog.entity.id, dialog.entity.access_hash), # type: ignore
                    settings=mute_settings
                ))
                print(f"Muted group: {dialog.name}") # type: ignore

    # Disconnect from the Telegram API
    await client.disconnect() # type: ignore

asyncio.run(main())
