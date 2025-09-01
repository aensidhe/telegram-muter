Let's implement unused settings: `weekends`, `working_weekends`, `nonworking_weekdays`.

For any manipulation with date, time, timezones use pendulum only.

Main goal of our program is to mute all groups till next working day and these settings help us understand when this next working day be.

So, we should make sure they are typed correctly. All dates is config can be only in ISO8601 format: YYYY-MM-DD. Anything else should lead to parse error and fail.

1. `weekends` is list of short names of weekdays in english: [Mon, Tue, Wed, Thu, Fri, Sat, Sun], or in russian: [Пн, Вт, Ср, Чт, Пт, Пн, Сб, Вс]. Anything else should lead to parse error and fail.
2. `working_weekends` and `nonworking_weekdays` are list of either dates or date intervals (below is the example, in the config we should follow toml grammar):
  - 2025-11-01 - means exactly one day, November 1st, 2025.
  - 2025-11-01, 2025-11-07 - means interval from November 1st till November 7th, including both sides, 2025 year.

Algorithm for getting next working day. You should go through it step by step, unless specified otherwise.

1. If time of now is less than `start_of_day` in specified timezone, then `starting day` should be today, else tomorrow.
2. If weekday of `starting day` is specified in the `weekends`, then it is `weekend`, otherwise it is `weekday`.
3. If it is `weekend` and it is specified in `working_weekends`, then is is `weekday`, else we should add 1 day to `starting day` and go to step 2.
4. If it is `weekday` and it is specified in `nonworking_weekdays` (see, this property has a priority over `working_weekends`, because hey, we can go to vacation), then we should add 1 day to `starting day` and go to step 2, else we have found our date.

Finally, please add tests for our algorithm and its integration with telegram API. Use pytest for that. You can add dependencies to `requirements.txt` and install them using `pip install -r`. Make sure you've activated virtualenv in `.direnv/python-3-....` (find it yourself under .direnv).

Tests should pass.

When they pass, please create README.md and README.en.md with description of the project and explanation of how to use it. Use russian for `README.md` and english for `README.en.md`.

If something is unclear, please ask before doing anything. 
