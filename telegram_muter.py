import asyncio
import argparse
from getpass import getpass
from telethon import TelegramClient
from telethon.errors.rpcerrorlist import SessionPasswordNeededError, FloodWaitError
from telethon.tl.functions.account import UpdateNotifySettingsRequest, GetNotifySettingsRequest
from telethon.tl.types import InputPeerNotifySettings, InputPeerChannel, Chat, InputPeerChat, User

from pydantic_settings import BaseSettings
from pydantic import Field, BaseModel, field_validator
from typing import List, Union, Any, Tuple, Optional
import pendulum
from pendulum import Time, WeekDay, Date
import tomllib
import re

class AuthSettings(BaseModel):
    api_id: int
    api_hash: str
    phone_number: str

class Schedule(BaseModel):
    name: str
    parent: str = Field(default="")
    start_of_day: Optional[Any] = Field(default=None)
    timezone: str = Field(default="")
    weekends: List[Any] = Field(default=[])
    working_weekends: List[Union[str, List[str]]] = Field(default=[])
    nonworking_weekdays: List[Union[str, List[str]]] = Field(default=[])

    @field_validator('start_of_day')
    @classmethod
    def parse_start_of_day(cls, v: Any) -> Optional[Time]:
        if v is None:
            return None
        if isinstance(v, Time):
            return v
        if isinstance(v, str):
            return pendulum.parse(v).time()
        raise ValueError(f"Cannot parse {v} as Time")

    @field_validator('weekends')
    @classmethod
    def parse_weekends(cls, v: Any) -> List[WeekDay]:
        if not v:  # Handle empty list or None
            return []
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

class GroupSetting(BaseModel):
    name: str = Field(default="")
    name_pattern: str = Field(default="")
    schedule: str

    def model_post_init(self, __context) -> None:
        if not self.name and not self.name_pattern:
            raise ValueError("Either 'name' or 'name_pattern' must be specified")
        if self.name and self.name_pattern:
            raise ValueError("'name' and 'name_pattern' are mutually exclusive")



class ScheduleManager:
    def __init__(self, schedules: List[Schedule], group_settings: List[GroupSetting] = None):
        self.schedules = {s.name: s for s in schedules}
        self.group_settings = group_settings or []
        
        # Validate schedules
        if 'default' not in self.schedules:
            raise ValueError("Schedule 'default' must be defined")
        
        # Validate parent references
        for schedule in schedules:
            if schedule.parent and schedule.parent not in self.schedules:
                raise ValueError(f"Schedule '{schedule.name}' references unknown parent '{schedule.parent}'")
        
        # Check for circular dependencies
        self._validate_no_circular_dependencies()

    def _validate_no_circular_dependencies(self):
        for schedule_name in self.schedules:
            visited = set()
            current = schedule_name
            
            while current:
                if current in visited:
                    raise ValueError(f"Circular dependency detected in schedule hierarchy involving '{schedule_name}'")
                visited.add(current)
                current = self.schedules[current].parent

    def _resolve_schedule_property(self, schedule_name: str, property_name: str):
        """Resolve a property value by walking up the parent chain"""
        current = schedule_name
        
        while current:
            schedule = self.schedules[current]
            value = getattr(schedule, property_name)
            
            # For start_of_day and timezone, check for None/"" specifically
            if property_name in ['start_of_day', 'timezone']:
                if value is not None and value != "":
                    return value
            # For lists, check if they're not empty
            elif isinstance(value, list) and value:
                return value
                
            current = schedule.parent
        
        # If we reach here without finding a value, return appropriate default
        if property_name == 'timezone':
            return "auto"
        elif property_name in ['weekends', 'working_weekends', 'nonworking_weekdays']:
            return []
        else:
            return None

    def get_effective_schedule(self, schedule_name: str) -> Schedule:
        """Get the effective schedule by resolving all properties through inheritance"""
        if schedule_name not in self.schedules:
            schedule_name = 'default'
        
        # Create an effective schedule by resolving all properties
        start_of_day_raw = self._resolve_schedule_property(schedule_name, 'start_of_day')
        timezone = self._resolve_schedule_property(schedule_name, 'timezone') 
        weekends_raw = self._resolve_schedule_property(schedule_name, 'weekends')
        working_weekends_raw = self._resolve_schedule_property(schedule_name, 'working_weekends')
        nonworking_weekdays_raw = self._resolve_schedule_property(schedule_name, 'nonworking_weekdays')
        
        # Convert resolved properties back to strings for Schedule creation
        start_of_day = start_of_day_raw.isoformat() if start_of_day_raw else "09:00:00"
        
        # Convert weekends back to strings
        weekends = []
        if weekends_raw:
            weekday_name_map = {
                WeekDay.MONDAY: "Mon", WeekDay.TUESDAY: "Tue", WeekDay.WEDNESDAY: "Wed",
                WeekDay.THURSDAY: "Thu", WeekDay.FRIDAY: "Fri", WeekDay.SATURDAY: "Sat", WeekDay.SUNDAY: "Sun"
            }
            for wd in weekends_raw:
                if isinstance(wd, WeekDay):
                    weekends.append(weekday_name_map[wd])
                else:
                    weekends.append(wd)
        
        # Convert date lists back to string format
        def convert_date_list_to_strings(date_list):
            if not date_list:
                return []
            result = []
            for item in date_list:
                if isinstance(item, Date):
                    result.append(item.isoformat())
                elif isinstance(item, tuple) and len(item) == 2:
                    result.append([item[0].isoformat(), item[1].isoformat()])
                else:
                    result.append(item)
            return result
        
        working_weekends = convert_date_list_to_strings(working_weekends_raw)
        nonworking_weekdays = convert_date_list_to_strings(nonworking_weekdays_raw)
        
        # Create effective schedule with resolved properties
        effective_schedule = Schedule(
            name=f"_effective_{schedule_name}",
            start_of_day=start_of_day,
            timezone=timezone or "auto",
            weekends=weekends,
            working_weekends=working_weekends,
            nonworking_weekdays=nonworking_weekdays
        )
        
        return effective_schedule

    def get_schedule_for_group(self, group_name: str) -> Schedule:
        """Get the appropriate schedule for a group based on group settings"""
        # First try exact name match
        for group_setting in self.group_settings:
            if group_setting.name and group_setting.name == group_name:
                return self.get_effective_schedule(group_setting.schedule)
        
        # Then try pattern match from top to bottom
        for group_setting in self.group_settings:
            if group_setting.name_pattern and re.match(group_setting.name_pattern, group_name):
                return self.get_effective_schedule(group_setting.schedule)
        
        # Default to 'default' schedule
        return self.get_effective_schedule('default')

class Settings(BaseSettings):
    auth: AuthSettings
    schedules: List[Schedule] = Field(default=[])
    group_settings: List[GroupSetting] = Field(default=[])

    def get_schedule_manager(self) -> ScheduleManager:
        """Get schedule manager"""
        if not self.schedules:
            raise ValueError("schedules must be defined")
        
        return ScheduleManager(self.schedules, self.group_settings)

def load_settings_from_toml(file_path: str) -> Settings:
    with open(file_path, "rb") as file:
        toml_content = tomllib.load(file)
    return Settings(**toml_content)

# Global settings - only load if config exists and we're not in test mode
try:
    import os
    if os.path.exists("config.toml") and 'pytest' not in os.environ.get('_', ''):
        settings = load_settings_from_toml("config.toml")
        schedule_manager = settings.get_schedule_manager()
    else:
        settings = None
        schedule_manager = None
except:
    settings = None
    schedule_manager = None

async def handle_rate_limit(operation, *args, **kwargs):
    """Common handler for Telegram rate limiting using FloodWaitError"""
    while True:
        try:
            return await operation(*args, **kwargs)
        except FloodWaitError as e:
            print(f"Rate limited by Telegram. Waiting {e.seconds} seconds...")
            await asyncio.sleep(e.seconds)

async def get_peer_for_dialog(dialog):
    """Get appropriate peer type for a dialog"""
    if isinstance(dialog.entity, Chat):
        return InputPeerChat(dialog.entity.id)
    elif hasattr(dialog.entity, 'broadcast') and not dialog.entity.broadcast:
        return InputPeerChannel(dialog.entity.id, dialog.entity.access_hash)
    return None

async def unmute_chats():
    """Unmute all chats that are muted until start_of_day next working day"""
    print("Starting unmute operation...")
    
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

    # Get default schedule for unmuting calculation  
    if settings is None:
        raise RuntimeError("Settings not loaded")
    schedule_manager_instance = settings.get_schedule_manager()
    default_schedule = schedule_manager_instance.get_effective_schedule('default')
    
    # Calculate the target mute_until time (start_of_day next working day)
    timezone_setting = default_schedule.timezone
    if timezone_setting == "auto":
        tz = pendulum.local_timezone()
    else:
        tz = pendulum.timezone(timezone_setting)

    next_working_day = default_schedule.get_next_working_day(timezone_setting)
    start_of_day = default_schedule.start_of_day

    target_mute_until = pendulum.datetime(
        next_working_day.year,
        next_working_day.month,
        next_working_day.day,
        start_of_day.hour,
        start_of_day.minute,
        start_of_day.second,
        tz=tz
    )

    print(f"Looking for chats muted until: {target_mute_until}")

    # Fetch all dialogs with pagination
    all_dialogs = await handle_rate_limit(client.get_dialogs, limit=None)

    unmuted_count = 0
    
    # Iterate through all dialogs and unmute matching chats
    for dialog in all_dialogs:
        peer = await get_peer_for_dialog(dialog)

        if peer is not None:
            # Check if the group is muted until the target time
            notify_settings = await handle_rate_limit(client, GetNotifySettingsRequest(peer=peer))
            
            if (notify_settings and 
                notify_settings.mute_until and 
                notify_settings.mute_until == target_mute_until):
                
                # Unmute the chat
                unmute_settings = InputPeerNotifySettings(
                    mute_until=None,
                    show_previews=True
                )
                await handle_rate_limit(client, UpdateNotifySettingsRequest(
                    peer=peer,
                    settings=unmute_settings
                ))
                print(f"Unmuted chat: {dialog.name}")
                unmuted_count += 1
            else:
                print(f"Skipped chat: {dialog.name} (not muted until target time)")
        else:
            if not isinstance(dialog.entity, User):
                print(f"Skipped: {dialog.name}, unknown peer type")

    print(f"Unmute operation completed. Total chats unmuted: {unmuted_count}")

    # Disconnect from the Telegram API
    await client.disconnect()

async def mute_chats():
    """Mute all unmuted chats until start_of_day next working day"""
    print("Starting mute operation...")
    
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

    # Fetch all dialogs with pagination first
    all_dialogs = await handle_rate_limit(client.get_dialogs, limit=None)

    muted_count = 0

    # Iterate through all dialogs and mute unmuted groups
    for dialog in all_dialogs:
        # Get appropriate schedule for this group
        if settings is None:
            raise RuntimeError("Settings not loaded")
        schedule_manager_instance = settings.get_schedule_manager()
        group_schedule = schedule_manager_instance.get_schedule_for_group(dialog.name)
        
        # Calculate the mute_until time for this specific group
        timezone_setting = group_schedule.timezone
        if timezone_setting == "auto":
            tz = pendulum.local_timezone()
        else:
            tz = pendulum.timezone(timezone_setting)

        now = pendulum.now(tz)
        next_working_day = group_schedule.get_next_working_day(timezone_setting)
        start_of_day = group_schedule.start_of_day

        mute_until = pendulum.datetime(
            next_working_day.year,
            next_working_day.month,
            next_working_day.day,
            start_of_day.hour,
            start_of_day.minute,
            start_of_day.second,
            tz=tz
        )
        
        print(f"Group '{dialog.name}' will be muted until: {mute_until}")
        
        peer = await get_peer_for_dialog(dialog)

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
                muted_count += 1
        else:
            if not isinstance(dialog.entity, User):
                print(f"Skipped: {dialog.name}, unknown peer type")

    print(f"Mute operation completed. Total chats muted: {muted_count}")

    # Disconnect from the Telegram API
    await client.disconnect()

async def main():
    parser = argparse.ArgumentParser(
        description="Telegram Muter - Mute/unmute Telegram chats until next working day"
    )
    parser.add_argument(
        "command", 
        choices=["mute", "unmute"], 
        nargs="?",
        default="mute",
        help="Command to execute (default: mute)"
    )
    
    args = parser.parse_args()
    
    if args.command == "mute":
        await mute_chats()
    elif args.command == "unmute":
        await unmute_chats()
    else:
        print(f"Unknown command: {args.command}")
        return 1
    
    return 0

if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code or 0)
