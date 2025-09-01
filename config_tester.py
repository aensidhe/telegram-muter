from pydantic_settings import BaseSettings
from pydantic import Field, BaseModel, field_validator
from typing import List, Union, Any, Tuple
import pendulum
from pendulum import Time, WeekDay, Date
import tomllib
import re

# Auth settings
class AuthSettings(BaseModel):
    api_id: int
    api_hash: str
    phone_number: str

# Time settings
class TimeSettings(BaseModel):
    start_of_day: Any = Field()
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
                # Map string to WeekDay enum
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

# Main settings
class Settings(BaseSettings):
    auth: AuthSettings
    time_settings: TimeSettings

def load_settings_from_toml(file_path: str) -> Settings:
    with open(file_path, "rb") as file:
        toml_content = tomllib.load(file)
    return Settings(**toml_content)

# Load settings from TOML file
settings = load_settings_from_toml("config.toml")

# Access settings
print(f"API ID: {settings.auth.api_id}")
print(f"API Hash: {settings.auth.api_hash}")
print(f"Phone Number: {settings.auth.phone_number}")
print(f"Start of the day: {settings.time_settings.start_of_day}")
print(f"Weekends: {settings.time_settings.weekends}")
print(f"Working weekends: {settings.time_settings.working_weekends}")
print(f"Nonworking weekdays (specific dates): {settings.time_settings.nonworking_weekdays}")
