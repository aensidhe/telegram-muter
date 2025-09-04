# Copyright (c) 2025-2025. aensidhe
#
# See LICENSE file.

from telegram_muter import Settings, load_settings_from_toml

# Load settings from TOML file
settings = load_settings_from_toml("config.toml")

# Get the schedule manager
schedule_manager = settings.get_schedule_manager()

# Access settings
print(f"API ID: {settings.auth.api_id}")
print(f"API Hash: {settings.auth.api_hash}")
print(f"Phone Number: {settings.auth.phone_number}")

print("\n=== All Effective Schedules ===")

# Print all defined schedules and their effective configurations
for schedule_name in schedule_manager.schedules.keys():
    effective_schedule = schedule_manager.get_effective_schedule(schedule_name)
    print(f"\nSchedule: {schedule_name}")
    print(f"  Start of the day: {effective_schedule.start_of_day}")
    print(f"  End of the day: {effective_schedule.end_of_day}")
    print(f"  Timezone: {effective_schedule.timezone}")
    print(f"  Weekends: {effective_schedule.weekends}")
    print(f"  Working weekends: {effective_schedule.working_weekends}")
    print(f"  Nonworking weekdays: {effective_schedule.nonworking_weekdays}")
    
    # Test next working day calculation
    next_working_day = effective_schedule.get_next_working_day()
    print(f"  Next working day: {next_working_day}")

print("\n=== Group Settings ===")
if settings.group_settings:
    for group_setting in settings.group_settings:
        print(f"Group: {group_setting.name or f'Pattern: {group_setting.name_pattern}'} -> Schedule: {group_setting.schedule}")
        effective_schedule = schedule_manager.get_effective_schedule(group_setting.schedule)
        print(f"  Effective start_of_day: {effective_schedule.start_of_day}")
        print(f"  Effective end_of_day: {effective_schedule.end_of_day}")
        print(f"  Effective timezone: {effective_schedule.timezone}")
else:
    print("No group-specific settings defined. All groups use 'default' schedule.")
