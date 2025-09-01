import asyncio
from getpass import getpass
from telethon import TelegramClient
from telethon.errors.rpcerrorlist import SessionPasswordNeededError, FloodWaitError
from telethon.tl.functions.account import UpdateNotifySettingsRequest, GetNotifySettingsRequest
from telethon.tl.types import InputPeerNotifySettings, InputPeerChannel, Chat, InputPeerChat, User

from pydantic_settings import BaseSettings
from pydantic import Field, BaseModel, field_validator
from typing import List, Union, Any, Tuple
import pendulum
from pendulum import Time, WeekDay, Date
import tomllib
import re

class AuthSettings(BaseModel):
    api_id: int
    api_hash: str
    phone_number: str

class TimeSettings(BaseModel):
    start_of_day: Any = Field()
    timezone: str = Field(default="auto")
    weekends: List[Any] = Field()
    working_weekends: List[Union[str, List[str]]] = Field(default=[])
    nonworking_weekdays: List[Union[str, List[str]]] = Field(default=[])

    @field_validator('start_of_day')
    @classmethod
    def parse_start_of_day(cls, v: Any) -> Time:
        if isinstance(v, Time):
            return v
        if isinstance(v, str):
            return pendulum.parse(v).time()
        raise ValueError(f"Cannot parse {v} as Time")

    @field_validator('weekends')
    @classmethod
    def parse_weekends(cls, v: Any) -> List[WeekDay]:
        if not isinstance(v, list):
            raise ValueError("weekends must be a list")

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
                    'Sun': WeekDay.SUNDAY,
                    'Пн': WeekDay.MONDAY,
                    'Вт': WeekDay.TUESDAY,
                    'Ср': WeekDay.WEDNESDAY,
                    'Чт': WeekDay.THURSDAY,
                    'Пт': WeekDay.FRIDAY,
                    'Сб': WeekDay.SATURDAY,
                    'Вс': WeekDay.SUNDAY
                }
                if item in weekday_map:
                    weekdays.append(weekday_map[item])
                else:
                    raise ValueError(f"Unknown weekday: {item}. Supported: {list(weekday_map.keys())}")
            else:
                raise ValueError(f"Cannot parse {item} as WeekDay")

        return weekdays

    @field_validator('working_weekends')
    @classmethod
    def parse_working_weekends(cls, v: Any) -> List[Union[Date, Tuple[Date, Date]]]:
        if not isinstance(v, list):
            raise ValueError("working_weekends must be a list")

        return cls._parse_date_list(v, "working_weekends")

    @field_validator('nonworking_weekdays')
    @classmethod
    def parse_nonworking_weekdays(cls, v: Any) -> List[Union[Date, Tuple[Date, Date]]]:
        if not isinstance(v, list):
            raise ValueError("nonworking_weekdays must be a list")

        return cls._parse_date_list(v, "nonworking_weekdays")

    @classmethod
    def _parse_date_list(cls, v: List[Union[str, List[str]]], field_name: str) -> List[Union[Date, Tuple[Date, Date]]]:
        parsed_dates = []

        for item in v:
            if isinstance(item, str):
                parsed_dates.append(cls._parse_iso_date(item, field_name))
            elif isinstance(item, list):
                if len(item) != 2:
                    raise ValueError(f"{field_name}: date interval must contain exactly 2 dates, got {len(item)}")
                start_date = cls._parse_iso_date(item[0], field_name)
                end_date = cls._parse_iso_date(item[1], field_name)
                if start_date > end_date:
                    raise ValueError(f"{field_name}: start date {item[0]} cannot be after end date {item[1]}")
                parsed_dates.append((start_date, end_date))
            else:
                raise ValueError(f"{field_name}: each item must be a string (single date) or list of 2 strings (date interval)")

        return parsed_dates

    @staticmethod
    def _parse_iso_date(date_str: str, field_name: str) -> Date:
        if not isinstance(date_str, str):
            raise ValueError(f"{field_name}: date must be a string in ISO8601 format (YYYY-MM-DD)")

        if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
            raise ValueError(f"{field_name}: date '{date_str}' must be in ISO8601 format (YYYY-MM-DD)")

        try:
            return pendulum.parse(date_str).date()
        except Exception as e:
            raise ValueError(f"{field_name}: invalid date '{date_str}': {e}")

    def get_next_working_day(self, timezone_setting: str = "auto") -> Date:
        if timezone_setting == "auto":
            tz = pendulum.local_timezone()
        else:
            tz = pendulum.timezone(timezone_setting)

        now = pendulum.now(tz)

        if now.time() < self.start_of_day:
            starting_day = now.date()
        else:
            starting_day = now.date().add(days=1)

        while True:
            weekday = starting_day.weekday()
            is_weekend = weekday in [wd.value for wd in self.weekends]

            # Check if this day is marked as nonworking (highest priority)
            if self._is_nonworking_date(starting_day):
                starting_day = starting_day.add(days=1)
                continue

            if is_weekend:
                # Weekend, but not nonworking - check if it's a working weekend
                if self._is_working_date(starting_day):
                    return starting_day
                else:
                    starting_day = starting_day.add(days=1)
                    continue
            else:
                # Regular weekday and not nonworking
                return starting_day

    def _is_working_date(self, date: Date) -> bool:
        for item in self.working_weekends:
            if isinstance(item, Date):
                if date == item:
                    return True
            elif isinstance(item, tuple):
                start_date, end_date = item
                if start_date <= date <= end_date:
                    return True
        return False

    def _is_nonworking_date(self, date: Date) -> bool:
        for item in self.nonworking_weekdays:
            if isinstance(item, Date):
                if date == item:
                    return True
            elif isinstance(item, tuple):
                start_date, end_date = item
                if start_date <= date <= end_date:
                    return True
        return False

class Settings(BaseSettings):
    auth: AuthSettings
    time_settings: TimeSettings

def load_settings_from_toml(file_path: str) -> Settings:
    with open(file_path, "rb") as file:
        toml_content = tomllib.load(file)
    return Settings(**toml_content)

settings = load_settings_from_toml("config.toml")

async def handle_rate_limit(operation, *args, **kwargs):
    """Common handler for Telegram rate limiting using FloodWaitError"""
    while True:
        try:
            return await operation(*args, **kwargs)
        except FloodWaitError as e:
            print(f"Rate limited by Telegram. Waiting {e.seconds} seconds...")
            await asyncio.sleep(e.seconds)

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

    # Calculate the mute_until time using the next working day algorithm
    timezone_setting = settings.time_settings.timezone
    if timezone_setting == "auto":
        tz = pendulum.local_timezone()
    else:
        tz = pendulum.timezone(timezone_setting)

    now = pendulum.now(tz)
    next_working_day = settings.time_settings.get_next_working_day(timezone_setting)
    start_of_day = settings.time_settings.start_of_day

    mute_until = pendulum.datetime(
        next_working_day.year,
        next_working_day.month,
        next_working_day.day,
        start_of_day.hour,
        start_of_day.minute,
        start_of_day.second,
        tz=tz
    )

    # Fetch all dialogs with pagination
    all_dialogs = await handle_rate_limit(client.get_dialogs, limit=None)

    # Iterate through all dialogs and mute unmuted groups
    for dialog in all_dialogs:
        peer : InputPeer = None

        if isinstance(dialog.entity, Chat):
            peer = InputPeerChat(dialog.entity.id)
        elif hasattr(dialog.entity, 'broadcast') and not dialog.entity.broadcast:
            peer = InputPeerChannel(dialog.entity.id, dialog.entity.access_hash)

        if peer is not None:
            # Check if the group is already muted
            notify_settings = await handle_rate_limit(client, GetNotifySettingsRequest(peer=peer))
            is_already_muted = (notify_settings and
                                notify_settings.mute_until and
                                notify_settings.mute_until > now)

            if is_already_muted:
                print(f"Skipping already muted chat: {dialog.name}")
            else:
                # Mute the group until start_of_day next day
                mute_settings = InputPeerNotifySettings(
                    mute_until=mute_until,
                    show_previews=False
                )
                await handle_rate_limit(client, UpdateNotifySettingsRequest(
                    peer=peer,
                    settings=mute_settings
                ))
                print(f"Muted chat: {dialog.name}")
        else:
            if not isinstance(dialog.entity, User):
                print(f"Skipped: {dialog.name}, unknown peer type")

    # Disconnect from the Telegram API
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
