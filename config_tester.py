from pydantic_settings import BaseSettings
from pydantic import Field, BaseModel, field_validator
from typing import List, Union, Any
import pendulum
from pendulum import Time, WeekDay
import tomllib

# Auth settings
class AuthSettings(BaseModel):
    api_id: int
    api_hash: str
    phone_number: str

# Time settings
class TimeSettings(BaseModel):
    start_of_day: Any = Field()
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
                # Map string to WeekDay enum
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
print(f"Nonworking weekdays: {settings.time_settings.nonworking_weekdays}")
print(f"Working weekends: {settings.time_settings.working_weekends}")
print(f"Nonworking weekdays (specific dates): {settings.time_settings.nonworking_weekdays_dates}")
