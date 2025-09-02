from telegram_muter import Settings, load_settings_from_toml

# Load settings from TOML file
settings = load_settings_from_toml("config.toml")

# Get the schedule manager and default schedule
schedule_manager = settings.get_schedule_manager()
default_schedule = schedule_manager.get_effective_schedule('default')

# Access settings
print(f"API ID: {settings.auth.api_id}")
print(f"API Hash: {settings.auth.api_hash}")
print(f"Phone Number: {settings.auth.phone_number}")
print(f"Start of the day: {default_schedule.start_of_day}")
print(f"Timezone: {default_schedule.timezone}")
print(f"Weekends: {default_schedule.weekends}")
print(f"Working weekends: {default_schedule.working_weekends}")
print(f"Nonworking weekdays (specific dates): {default_schedule.nonworking_weekdays}")

# Test next working day calculation
next_working_day = default_schedule.get_next_working_day()
print(f"Next working day: {next_working_day}")
