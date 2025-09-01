# Telegram Muter

A utility for automatically muting Telegram group notifications until the next working day.

## Description

Telegram Muter is a Python application that connects to the Telegram API and mutes notifications for all groups until the start of the next working day. The application supports complex working day determination logic, accounting for weekends, working weekends, and non-working weekdays.

## Features

- **Smart next working day calculation** considering:
  - Regular weekend days (Saturday and Sunday by default)
  - Working weekends (e.g., Saturday that should be treated as a working day)
  - Non-working weekdays (e.g., holidays)
  - Time zones
  - Work start time
  
- **Support for Russian and English day names**
- **Telegram API rate limiting handling**
- **Skips already muted groups**
- **Detailed process logging**

## Working Day Determination Algorithm

1. If current time is less than `start_of_day` in the specified timezone, then `starting day` should be today, else tomorrow.
2. If weekday of `starting day` is specified in `weekends`, then it is a `weekend`, otherwise it is a `weekday`.
3. If it is a `weekend` and it is specified in `working_weekends`, then it is a `weekday`, else add 1 day to `starting day` and go to step 2.
4. If it is a `weekday` and it is specified in `nonworking_weekdays` (this property has priority over `working_weekends`), then add 1 day to `starting day` and go to step 2, else we have found our date.

## Installation

1. Clone the repository:
```bash
git clone https://github.com/aensidhe/telegram-muter.git
cd telegram-muter
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create configuration file:
```bash
cp config.template.toml config.toml
```

4. Configure `config.toml`:
```toml
[auth]
api_id = 12345  # Your API ID from https://my.telegram.org
api_hash = "your_api_hash"  # Your API Hash
phone_number = "+1234567890"  # Your phone number

[time_settings]
start_of_day = "10:00:00"  # Work day start time
timezone = "auto"  # "auto" for system timezone or "Europe/London"
weekends = ["Sat", "Sun"]  # Weekend days (supported: Mon, Tue, Wed, Thu, Fri, Sat, Sun, Пн, Вт, Ср, Чт, Пт, Сб, Вс)

# Working weekends (specific dates or date intervals)
working_weekends = [
    "2025-11-01",  # Single date
    ["2025-12-25", "2025-12-31"]  # Date interval
]

# Non-working weekdays (specific dates or date intervals)
nonworking_weekdays = [
    "2025-12-31",  # New Year's Eve
    ["2026-01-01", "2026-01-07"]  # New Year holidays
]
```

## Usage

Run the application:
```bash
python from_telethon.py
```

On first run you will need to:
1. Enter verification code from SMS
2. If needed, enter two-factor authentication password

## Date and Time Formats

- **Time**: HH:MM:SS format (e.g., "10:00:00")
- **Dates**: ISO8601 YYYY-MM-DD format only (e.g., "2025-12-31")
- **Weekdays**: 
  - English: Mon, Tue, Wed, Thu, Fri, Sat, Sun
  - Russian: Пн, Вт, Ср, Чт, Пт, Сб, Вс
- **Date intervals**: Array of two dates `["2025-12-25", "2025-12-31"]` (both boundaries inclusive)

## Testing

Run tests:
```bash
# Run all tests
pytest

# Run specific tests
pytest test_working_days.py -v
pytest test_integration.py -v
```

## Project Structure

- `from_telethon.py` — main application file
- `config_tester.py` — configuration testing utility
- `config.template.toml` — configuration template
- `test_working_days.py` — working day algorithm tests
- `test_integration.py` — integration tests
- `requirements.txt` — Python dependencies

## Requirements

- Python 3.8+
- Telegram API credentials (get them at https://my.telegram.org)
- Active Telegram account

## License

MIT License

## Support

If you encounter any issues or have questions, please create an issue in the GitHub repository.
