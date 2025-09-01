# -*- coding: utf-8 -*-
import pytest
import pendulum
from pendulum import WeekDay, Date
from unittest.mock import patch
from pydantic import ValidationError

from telegram_muter import TimeSettings, Settings, AuthSettings, Schedule, ScheduleManager, GroupSetting


class TestTimeSettingsValidation:

    def test_weekends_english_names(self):
        """Test parsing English weekday names"""
        settings = TimeSettings(
            start_of_day="10:00:00",
            weekends=["Sat", "Sun"],
            working_weekends=[],
            nonworking_weekdays=[]
        )
        assert settings.weekends == [WeekDay.SATURDAY, WeekDay.SUNDAY]

    def test_weekends_russian_names(self):
        """Test parsing Russian weekday names"""
        settings = TimeSettings(
            start_of_day="10:00:00",
            weekends=["Сб", "Вс"],
            working_weekends=[],
            nonworking_weekdays=[]
        )
        assert settings.weekends == [WeekDay.SATURDAY, WeekDay.SUNDAY]

    def test_weekends_mixed_names(self):
        """Test parsing mixed English and Russian weekday names"""
        settings = TimeSettings(
            start_of_day="10:00:00",
            weekends=["Mon", "Вт", "Wed", "Чт", "Fri"],
            working_weekends=[],
            nonworking_weekdays=[]
        )
        assert settings.weekends == [WeekDay.MONDAY, WeekDay.TUESDAY, WeekDay.WEDNESDAY, WeekDay.THURSDAY, WeekDay.FRIDAY]

    def test_weekends_invalid_name(self):
        """Test validation error for invalid weekday name"""
        with pytest.raises(ValidationError) as exc_info:
            TimeSettings(
                start_of_day="10:00:00",
                weekends=["InvalidDay"],
                working_weekends=[],
                nonworking_weekdays=[]
            )
        assert "Unknown weekday: InvalidDay" in str(exc_info.value)

    def test_working_weekends_single_date(self):
        """Test parsing single date in working_weekends"""
        settings = TimeSettings(
            start_of_day="10:00:00",
            weekends=["Sat", "Sun"],
            working_weekends=["2025-11-01"],
            nonworking_weekdays=[]
        )
        assert len(settings.working_weekends) == 1
        assert isinstance(settings.working_weekends[0], Date)
        assert settings.working_weekends[0] == pendulum.parse("2025-11-01").date()

    def test_working_weekends_date_interval(self):
        """Test parsing date interval in working_weekends"""
        settings = TimeSettings(
            start_of_day="10:00:00",
            weekends=["Sat", "Sun"],
            working_weekends=[["2025-11-01", "2025-11-07"]],
            nonworking_weekdays=[]
        )
        assert len(settings.working_weekends) == 1
        assert isinstance(settings.working_weekends[0], tuple)
        start_date, end_date = settings.working_weekends[0]
        assert start_date == pendulum.parse("2025-11-01").date()
        assert end_date == pendulum.parse("2025-11-07").date()

    def test_working_weekends_invalid_date_format(self):
        """Test validation error for invalid date format"""
        with pytest.raises(ValidationError) as exc_info:
            TimeSettings(
                start_of_day="10:00:00",
                weekends=["Sat", "Sun"],
                working_weekends=["2025/11/01"],
                nonworking_weekdays=[]
            )
        assert "must be in ISO8601 format (YYYY-MM-DD)" in str(exc_info.value)

    def test_working_weekends_invalid_date(self):
        """Test validation error for invalid date"""
        with pytest.raises(ValidationError) as exc_info:
            TimeSettings(
                start_of_day="10:00:00",
                weekends=["Sat", "Sun"],
                working_weekends=["2025-13-01"],  # Invalid month
                nonworking_weekdays=[]
            )
        assert "invalid date '2025-13-01'" in str(exc_info.value)

    def test_working_weekends_interval_wrong_order(self):
        """Test validation error when start date is after end date"""
        with pytest.raises(ValidationError) as exc_info:
            TimeSettings(
                start_of_day="10:00:00",
                weekends=["Sat", "Sun"],
                working_weekends=[["2025-11-07", "2025-11-01"]],  # Wrong order
                nonworking_weekdays=[]
            )
        assert "start date 2025-11-07 cannot be after end date 2025-11-01" in str(exc_info.value)

    def test_working_weekends_interval_wrong_length(self):
        """Test validation error for interval with wrong number of dates"""
        with pytest.raises(ValidationError) as exc_info:
            TimeSettings(
                start_of_day="10:00:00",
                weekends=["Sat", "Sun"],
                working_weekends=[["2025-11-01", "2025-11-07", "2025-11-15"]],  # 3 dates instead of 2
                nonworking_weekdays=[]
            )
        assert "date interval must contain exactly 2 dates" in str(exc_info.value)

    def test_nonworking_weekdays_validation(self):
        """Test nonworking_weekdays follows same validation rules"""
        settings = TimeSettings(
            start_of_day="10:00:00",
            weekends=["Sat", "Sun"],
            working_weekends=[],
            nonworking_weekdays=["2025-12-31", ["2026-01-01", "2026-01-07"]]
        )
        assert len(settings.nonworking_weekdays) == 2
        assert isinstance(settings.nonworking_weekdays[0], Date)
        assert isinstance(settings.nonworking_weekdays[1], tuple)


class TestNextWorkingDayAlgorithm:

    def create_settings(self, weekends=None, working_weekends=None, nonworking_weekdays=None):
        """Helper method to create TimeSettings for testing"""
        return TimeSettings(
            start_of_day="10:00:00",
            weekends=weekends or ["Sat", "Sun"],
            working_weekends=working_weekends or [],
            nonworking_weekdays=nonworking_weekdays or []
        )

    @patch('pendulum.now')
    def test_before_start_of_day_weekday(self, mock_now):
        """Test when current time is before start_of_day on a weekday"""
        # Mock current time: Friday 9:00 AM
        mock_time = pendulum.parse("2025-09-05T09:00:00")  # Friday
        mock_now.return_value = mock_time
        
        settings = self.create_settings()
        next_day = settings.get_next_working_day()
        
        # Should be today (Friday) since it's before 10:00 and Friday is not a weekend
        assert next_day == mock_time.date()

    @patch('pendulum.now')
    def test_after_start_of_day_weekday(self, mock_now):
        """Test when current time is after start_of_day on a weekday"""
        # Mock current time: Friday 11:00 AM
        mock_time = pendulum.parse("2025-09-05T11:00:00")  # Friday
        mock_now.return_value = mock_time
        
        settings = self.create_settings()
        next_day = settings.get_next_working_day()
        
        # Should be next Monday (since Sat/Sun are weekends)
        expected = pendulum.parse("2025-09-08").date()  # Monday
        assert next_day == expected

    @patch('pendulum.now')
    def test_weekend_no_working_weekend(self, mock_now):
        """Test weekend without working_weekends"""
        # Mock current time: Saturday 9:00 AM
        mock_time = pendulum.parse("2025-09-06T09:00:00")  # Saturday
        mock_now.return_value = mock_time
        
        settings = self.create_settings()
        next_day = settings.get_next_working_day()
        
        # Should be next Monday
        expected = pendulum.parse("2025-09-08").date()  # Monday
        assert next_day == expected

    @patch('pendulum.now')
    def test_weekend_with_working_weekend_single_date(self, mock_now):
        """Test weekend that is specified as working day (single date)"""
        # Mock current time: Saturday 9:00 AM
        mock_time = pendulum.parse("2025-09-06T09:00:00")  # Saturday
        mock_now.return_value = mock_time
        
        settings = self.create_settings(working_weekends=["2025-09-06"])  # Saturday is working
        next_day = settings.get_next_working_day()
        
        # Should be today (Saturday) since it's marked as working
        assert next_day == mock_time.date()

    @patch('pendulum.now')
    def test_weekend_with_working_weekend_interval(self, mock_now):
        """Test weekend that is specified as working day (interval)"""
        # Mock current time: Saturday 9:00 AM
        mock_time = pendulum.parse("2025-09-06T09:00:00")  # Saturday
        mock_now.return_value = mock_time
        
        settings = self.create_settings(working_weekends=[["2025-09-06", "2025-09-07"]])  # Weekend interval
        next_day = settings.get_next_working_day()
        
        # Should be today (Saturday) since it's in working interval
        assert next_day == mock_time.date()

    @patch('pendulum.now')
    def test_weekday_with_nonworking_weekday(self, mock_now):
        """Test weekday that is specified as nonworking"""
        # Mock current time: Friday 9:00 AM
        mock_time = pendulum.parse("2025-09-05T09:00:00")  # Friday
        mock_now.return_value = mock_time
        
        settings = self.create_settings(nonworking_weekdays=["2025-09-05"])  # Friday is vacation
        next_day = settings.get_next_working_day()
        
        # Should be next Monday (skipping nonworking Friday and weekend)
        expected = pendulum.parse("2025-09-08").date()  # Monday
        assert next_day == expected

    @patch('pendulum.now')
    def test_nonworking_weekday_overrides_working_weekend(self, mock_now):
        """Test that nonworking_weekdays has priority over working_weekends"""
        # Mock current time: Saturday 9:00 AM
        mock_time = pendulum.parse("2025-09-06T09:00:00")  # Saturday
        mock_now.return_value = mock_time
        
        settings = self.create_settings(
            working_weekends=["2025-09-06"],  # Saturday should be working
            nonworking_weekdays=["2025-09-06"]  # But it's vacation (higher priority)
        )
        next_day = settings.get_next_working_day()
        
        # Should be next Monday (nonworking_weekdays overrides working_weekends)
        expected = pendulum.parse("2025-09-08").date()  # Monday
        assert next_day == expected

    @patch('pendulum.now')
    def test_complex_scenario(self, mock_now):
        """Test complex scenario with multiple rules"""
        # Mock current time: Thursday 11:00 PM (after start_of_day)
        mock_time = pendulum.parse("2025-09-04T23:00:00")  # Thursday
        mock_now.return_value = mock_time
        
        settings = self.create_settings(
            working_weekends=["2025-09-06"],  # Saturday is working
            nonworking_weekdays=["2025-09-05"]  # Friday is vacation
        )
        next_day = settings.get_next_working_day()
        
        # Starting day would be Friday (after start_of_day), but Friday is vacation
        # Saturday is weekend but marked as working, so should be Saturday
        expected = pendulum.parse("2025-09-06").date()  # Saturday
        assert next_day == expected

    @patch('pendulum.now')
    def test_long_vacation_period(self, mock_now):
        """Test finding next working day after long vacation period"""
        # Mock current time: Monday 9:00 AM
        mock_time = pendulum.parse("2025-12-29T09:00:00")  # Monday
        mock_now.return_value = mock_time
        
        settings = self.create_settings(
            nonworking_weekdays=[
                ["2025-12-29", "2026-01-05"]  # Long vacation including weekends
            ]
        )
        next_day = settings.get_next_working_day()
        
        # Should find first working day after vacation period
        expected = pendulum.parse("2026-01-06").date()  # Monday after vacation
        assert next_day == expected

    def test_timezone_support(self):
        """Test that timezone parameter works correctly"""
        settings = self.create_settings()
        
        # Should not raise error with valid timezone
        next_day = settings.get_next_working_day("Europe/London")
        assert isinstance(next_day, Date)
        
        # Should not raise error with auto timezone
        next_day = settings.get_next_working_day("auto")
        assert isinstance(next_day, Date)


class TestDateHelperMethods:

    def test_is_working_date_single_date(self):
        """Test _is_working_date with single date"""
        settings = TimeSettings(
            start_of_day="10:00:00",
            weekends=["Sat", "Sun"],
            working_weekends=["2025-09-06"],
            nonworking_weekdays=[]
        )
        
        test_date = pendulum.parse("2025-09-06").date()
        assert settings._is_working_date(test_date) is True
        
        other_date = pendulum.parse("2025-09-07").date()
        assert settings._is_working_date(other_date) is False

    def test_is_working_date_interval(self):
        """Test _is_working_date with date interval"""
        settings = TimeSettings(
            start_of_day="10:00:00",
            weekends=["Sat", "Sun"],
            working_weekends=[["2025-09-06", "2025-09-08"]],
            nonworking_weekdays=[]
        )
        
        # Dates within interval should be working
        for day in [6, 7, 8]:
            test_date = pendulum.parse(f"2025-09-{day:02d}").date()
            assert settings._is_working_date(test_date) is True
        
        # Dates outside interval should not be working
        test_date = pendulum.parse("2025-09-05").date()
        assert settings._is_working_date(test_date) is False
        
        test_date = pendulum.parse("2025-09-09").date()
        assert settings._is_working_date(test_date) is False

    def test_is_nonworking_date_single_date(self):
        """Test _is_nonworking_date with single date"""
        settings = TimeSettings(
            start_of_day="10:00:00",
            weekends=["Sat", "Sun"],
            working_weekends=[],
            nonworking_weekdays=["2025-09-05"]
        )
        
        test_date = pendulum.parse("2025-09-05").date()
        assert settings._is_nonworking_date(test_date) is True
        
        other_date = pendulum.parse("2025-09-06").date()
        assert settings._is_nonworking_date(other_date) is False

    def test_is_nonworking_date_interval(self):
        """Test _is_nonworking_date with date interval"""
        settings = TimeSettings(
            start_of_day="10:00:00",
            weekends=["Sat", "Sun"],
            working_weekends=[],
            nonworking_weekdays=[["2025-12-25", "2025-12-31"]]
        )
        
        # Dates within interval should be nonworking
        for day in [25, 26, 27, 28, 29, 30, 31]:
            test_date = pendulum.parse(f"2025-12-{day:02d}").date()
            assert settings._is_nonworking_date(test_date) is True
        
        # Dates outside interval should be working
        test_date = pendulum.parse("2025-12-24").date()
        assert settings._is_nonworking_date(test_date) is False
        
        test_date = pendulum.parse("2026-01-01").date()
        assert settings._is_nonworking_date(test_date) is False


class TestScheduleSystem:

    def test_schedule_creation(self):
        """Test basic schedule creation"""
        schedule = Schedule(
            name="test",
            start_of_day="09:00:00",
            timezone="Europe/London",
            weekends=["Sat", "Sun"]
        )
        assert schedule.name == "test"
        assert schedule.timezone == "Europe/London"
        assert schedule.weekends == [WeekDay.SATURDAY, WeekDay.SUNDAY]

    def test_schedule_inheritance_single_level(self):
        """Test schedule inheritance with one parent"""
        default_schedule = Schedule(name="default", start_of_day="08:00:00", weekends=["Mon"])
        
        base_schedule = Schedule(
            name="base",
            start_of_day="09:00:00",
            timezone="UTC",
            weekends=["Sat", "Sun"],
            working_weekends=["2025-12-25"]
        )
        
        child_schedule = Schedule(
            name="child",
            parent="base",
            start_of_day="10:00:00"  # Override only start_of_day
        )
        
        manager = ScheduleManager([default_schedule, base_schedule, child_schedule])
        effective = manager.get_effective_schedule("child")
        
        # Should inherit most from parent but override start_of_day
        assert effective.start_of_day.hour == 10
        assert effective.timezone == "UTC"
        assert effective.weekends == [WeekDay.SATURDAY, WeekDay.SUNDAY]
        assert len(effective.working_weekends) == 1

    def test_schedule_inheritance_multi_level(self):
        """Test schedule inheritance with multiple levels"""
        default_schedule = Schedule(name="default", start_of_day="07:00:00", weekends=["Fri"])
        
        grandparent = Schedule(
            name="grandparent",
            start_of_day="08:00:00",
            timezone="UTC",
            weekends=["Sat", "Sun"],
            working_weekends=["2025-12-25"],
            nonworking_weekdays=["2025-01-01"]
        )
        
        parent = Schedule(
            name="parent",
            parent="grandparent",
            start_of_day="09:00:00",
            timezone="Europe/London"
        )
        
        child = Schedule(
            name="child",
            parent="parent",
            weekends=["Sun"]  # Only Sunday as weekend
        )
        
        manager = ScheduleManager([default_schedule, grandparent, parent, child])
        effective = manager.get_effective_schedule("child")
        
        # Should get start_of_day and timezone from parent, weekends from child, dates from grandparent
        assert effective.start_of_day.hour == 9
        assert effective.timezone == "Europe/London"
        assert effective.weekends == [WeekDay.SUNDAY]
        assert len(effective.working_weekends) == 1
        assert len(effective.nonworking_weekdays) == 1

    def test_default_schedule_required(self):
        """Test that 'default' schedule is required"""
        schedule = Schedule(name="not_default", start_of_day="09:00:00", weekends=["Sun"])
        
        with pytest.raises(ValueError, match="Schedule 'default' must be defined"):
            ScheduleManager([schedule])

    def test_parent_validation(self):
        """Test validation of parent references"""
        schedule = Schedule(name="default", parent="nonexistent", start_of_day="09:00:00", weekends=["Sun"])
        
        with pytest.raises(ValueError, match="references unknown parent 'nonexistent'"):
            ScheduleManager([schedule])

    def test_circular_dependency_detection(self):
        """Test detection of circular dependencies"""
        schedule1 = Schedule(name="default", parent="child", start_of_day="09:00:00", weekends=["Sun"])
        schedule2 = Schedule(name="child", parent="default", start_of_day="10:00:00", weekends=["Mon"])
        
        with pytest.raises(ValueError, match="Circular dependency detected"):
            ScheduleManager([schedule1, schedule2])

    def test_group_settings_validation(self):
        """Test GroupSetting validation"""
        # Should require either name or name_pattern
        with pytest.raises(ValueError, match="Either 'name' or 'name_pattern' must be specified"):
            GroupSetting(schedule="default")
        
        # Should not allow both name and name_pattern
        with pytest.raises(ValueError, match="'name' and 'name_pattern' are mutually exclusive"):
            GroupSetting(name="test", name_pattern="test.*", schedule="default")

    def test_group_schedule_matching_exact_name(self):
        """Test group schedule matching by exact name"""
        default_schedule = Schedule(name="default", start_of_day="09:00:00", weekends=["Sat", "Sun"])
        work_schedule = Schedule(name="work", start_of_day="08:00:00", weekends=["Sun"])
        
        group_settings = [
            GroupSetting(name="Work Chat", schedule="work"),
            GroupSetting(name="Other Chat", schedule="default")
        ]
        
        manager = ScheduleManager([default_schedule, work_schedule], group_settings)
        
        # Should match exact name
        work_effective = manager.get_schedule_for_group("Work Chat")
        assert work_effective.start_of_day.hour == 8
        
        # Should match other exact name
        other_effective = manager.get_schedule_for_group("Other Chat")
        assert other_effective.start_of_day.hour == 9

    def test_group_schedule_matching_pattern(self):
        """Test group schedule matching by regex pattern"""
        default_schedule = Schedule(name="default", start_of_day="09:00:00", weekends=["Sat", "Sun"])
        duty_schedule = Schedule(name="duty", start_of_day="00:00:00", weekends=[])
        
        group_settings = [
            GroupSetting(name_pattern="duty.*", schedule="duty")
        ]
        
        manager = ScheduleManager([default_schedule, duty_schedule], group_settings)
        
        # Should match pattern
        duty_effective = manager.get_schedule_for_group("duty_chat")
        assert duty_effective.start_of_day.hour == 0
        assert duty_effective.weekends == []
        
        # Should not match pattern, use default
        normal_effective = manager.get_schedule_for_group("normal_chat")
        assert normal_effective.start_of_day.hour == 9

    def test_group_schedule_matching_priority(self):
        """Test that exact name match takes priority over pattern match"""
        default_schedule = Schedule(name="default", start_of_day="09:00:00", weekends=["Sat", "Sun"])
        exact_schedule = Schedule(name="exact", start_of_day="10:00:00", weekends=["Sun"])
        pattern_schedule = Schedule(name="pattern", start_of_day="11:00:00", weekends=["Sat"])
        
        group_settings = [
            GroupSetting(name_pattern="test.*", schedule="pattern"),
            GroupSetting(name="test_group", schedule="exact")  # Exact match should win
        ]
        
        manager = ScheduleManager([default_schedule, exact_schedule, pattern_schedule], group_settings)
        
        # Exact match should take priority
        effective = manager.get_schedule_for_group("test_group")
        assert effective.start_of_day.hour == 10

    def test_backward_compatibility(self):
        """Test backward compatibility with old time_settings format"""
        auth = AuthSettings(api_id=123, api_hash="hash", phone_number="+123456789")
        time_settings = TimeSettings(
            start_of_day="09:00:00",
            timezone="UTC",
            weekends=["Sat", "Sun"],
            working_weekends=["2025-12-25"],
            nonworking_weekdays=["2025-01-01"]
        )
        
        settings = Settings(auth=auth, time_settings=time_settings)
        manager = settings.get_schedule_manager()
        
        # Should create a default schedule from time_settings
        effective = manager.get_effective_schedule("default")
        assert effective.start_of_day.hour == 9
        assert effective.timezone == "UTC"
        assert effective.weekends == [WeekDay.SATURDAY, WeekDay.SUNDAY]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
