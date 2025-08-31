import asyncio
from datetime import datetime, timedelta
from getpass import getpass
from telethon import TelegramClient
from telethon.errors.rpcerrorlist import SessionPasswordNeededError
from telethon.tl.functions.account import UpdateNotifySettingsRequest
from telethon.tl.types import InputPeerNotifySettings, InputPeerChannel

from pydantic_settings import BaseSettings
from pydantic import Field, BaseModel, field_validator
from typing import List, Union, Any
import pendulum
from pendulum import Time, WeekDay
import tomllib

class AuthSettings(BaseModel):
    api_id: int
    api_hash: str
    phone_number: str

class TimeSettings(BaseModel):
    start_of_day: Any = Field()
    timezone: str = Field(default="auto")
    nonworking_weekdays: List[Any] = Field()
    working_weekends: List[Union[str, List[str]]] = Field()
    nonworking_weekdays_dates: List[Union[str, List[str]]] = Field()

    @field_validator('start_of_day')
    @classmethod
    def parse_start_of_day(cls, v: Any) -> Time:
        if isinstance(v, Time):
            return v
        if isinstance(v, str):
            return pendulum.parse(v).time()
        raise ValueError(f"Cannot parse {v} as Time")

    @field_validator('nonworking_weekdays')
    @classmethod
    def parse_nonworking_weekdays(cls, v: Any) -> List[WeekDay]:
        if not isinstance(v, list):
            raise ValueError("nonworking_weekdays must be a list")

        weekdays = []
        for item in v:
            if isinstance(item, WeekDay):
                weekdays.append(item)
            elif isinstance(item, str):
                weekday_map = {
                    'Mon': WeekDay.MONDAY,
                    'Tue': WeekDay.TUESDAY,
                    'Wed': WeekDay.WEDNESDAY,
                    'Thu': WeekDay.THURSDAY,
                    'Fri': WeekDay.FRIDAY,
                    'Sat': WeekDay.SATURDAY,
                    'Sun': WeekDay.SUNDAY
                }
                if item in weekday_map:
                    weekdays.append(weekday_map[item])
                else:
                    raise ValueError(f"Unknown weekday: {item}")
            else:
                raise ValueError(f"Cannot parse {item} as WeekDay")

        return weekdays

class Settings(BaseSettings):
    auth: AuthSettings
    time_settings: TimeSettings

def load_settings_from_toml(file_path: str) -> Settings:
    with open(file_path, "rb") as file:
        toml_content = tomllib.load(file)
    return Settings(**toml_content)

settings = load_settings_from_toml("config.toml")

async def main():
    # Connect to the Telegram API
    client = TelegramClient('ru.aensidhe.console_groups_muter', settings.auth.api_id, settings.auth.api_hash)
    await client.connect()

    # Ensure you're authorized
    if not await client.is_user_authorized():
        await client.send_code_request(settings.auth.phone_number)
        try:
            await client.sign_in(settings.auth.phone_number, input('Enter the code: '))
        except SessionPasswordNeededError:
            await client.sign_in(settings.auth.phone_number, password=getpass('Enter 2FA password: '))

    # Calculate the mute_until time using start_of_day from config with timezone support
    timezone_setting = settings.time_settings.timezone
    if timezone_setting == "auto":
        # Use system local timezone
        tz = pendulum.local_timezone()
    else:
        # Use specified timezone
        tz = pendulum.timezone(timezone_setting)

    now = pendulum.now(tz)
    start_of_day = settings.time_settings.start_of_day
    mute_until = now.replace(hour=start_of_day.hour, minute=start_of_day.minute, second=start_of_day.second, microsecond=0).add(days=1)

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
