# -*- coding: utf-8 -*-
import pytest
import pendulum
from pendulum import WeekDay, Date
from unittest.mock import patch
from pydantic import ValidationError

from telegram_muter import Settings, AuthSettings, Schedule, ScheduleManager, GroupSetting


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


class TestGetNextWorkingDay:
    """Test the get_next_working_day method logic"""
    
    def test_before_start_of_day_weekday(self):
        """Test when current time is before start_of_day on a weekday"""
        # Create schedule with start_of_day at 09:00
        schedule = Schedule(
            name="default",
            start_of_day="09:00:00",
            timezone="UTC",
            weekends=["Sat", "Sun"]
        )
        
        # Mock current time to Wednesday 08:00 (before start_of_day)
        with patch('pendulum.now') as mock_now:
            # Wednesday, Jan 8, 2025 08:00 UTC
            mock_now.return_value = pendulum.parse("2025-01-08T08:00:00+00:00")
            
            result = schedule.get_next_working_day("UTC")
            
            # Should return today (Jan 8, 2025) since it's before start_of_day and it's a weekday
            expected = Date(2025, 1, 8)
            assert result == expected
    
    def test_after_start_of_day_weekday(self):
        """Test when current time is after start_of_day on a weekday"""
        schedule = Schedule(
            name="default",
            start_of_day="09:00:00",
            timezone="UTC",
            weekends=["Sat", "Sun"]
        )
        
        # Mock current time to Wednesday 10:00 (after start_of_day)
        with patch('pendulum.now') as mock_now:
            # Wednesday, Jan 8, 2025 10:00 UTC
            mock_now.return_value = pendulum.parse("2025-01-08T10:00:00+00:00")
            
            result = schedule.get_next_working_day("UTC")
            
            # Should return tomorrow (Jan 9, 2025) since it's after start_of_day
            expected = Date(2025, 1, 9)
            assert result == expected
    
    def test_before_start_of_day_weekend_no_working_weekend(self):
        """Test when current time is before start_of_day on a weekend with no working weekend"""
        schedule = Schedule(
            name="default",
            start_of_day="09:00:00",
            timezone="UTC",
            weekends=["Sat", "Sun"]
        )
        
        # Mock current time to Saturday 08:00 (before start_of_day, weekend)
        with patch('pendulum.now') as mock_now:
            # Saturday, Jan 11, 2025 08:00 UTC
            mock_now.return_value = pendulum.parse("2025-01-11T08:00:00+00:00")
            
            result = schedule.get_next_working_day("UTC")
            
            # Should return Monday (Jan 13, 2025) since weekend days are skipped
            expected = Date(2025, 1, 13)
            assert result == expected
    
    def test_weekend_with_working_weekend_date(self):
        """Test weekend day that is specified as working in working_weekends"""
        schedule = Schedule(
            name="default",
            start_of_day="09:00:00",
            timezone="UTC",
            weekends=["Sat", "Sun"],
            working_weekends=["2025-01-11"]  # Saturday Jan 11
        )
        
        # Mock current time to Saturday 08:00 (before start_of_day, weekend but working)
        with patch('pendulum.now') as mock_now:
            # Saturday, Jan 11, 2025 08:00 UTC
            mock_now.return_value = pendulum.parse("2025-01-11T08:00:00+00:00")
            
            result = schedule.get_next_working_day("UTC")
            
            # Should return today (Jan 11, 2025) since it's a working weekend
            expected = Date(2025, 1, 11)
            assert result == expected
    
    def test_weekend_with_working_weekend_range(self):
        """Test weekend day that is specified as working in a date range"""
        schedule = Schedule(
            name="default",
            start_of_day="09:00:00",
            timezone="UTC",
            weekends=["Sat", "Sun"],
            working_weekends=[["2025-01-10", "2025-01-12"]]  # Range covering the Sunday
        )
        
        # Mock current time to Sunday 08:00 (before start_of_day, weekend but in working range)
        with patch('pendulum.now') as mock_now:
            # Sunday, Jan 12, 2025 08:00 UTC
            mock_now.return_value = pendulum.parse("2025-01-12T08:00:00+00:00")
            
            result = schedule.get_next_working_day("UTC")
            
            # Should return today (Jan 12, 2025) since it's in the working weekend range
            expected = Date(2025, 1, 12)
            assert result == expected
    
    def test_weekday_with_nonworking_weekday_date(self):
        """Test weekday that is specified as nonworking (vacation)"""
        schedule = Schedule(
            name="default",
            start_of_day="09:00:00",
            timezone="UTC",
            weekends=["Sat", "Sun"],
            nonworking_weekdays=["2025-01-08"]  # Wednesday Jan 8
        )
        
        # Mock current time to Wednesday 08:00 (before start_of_day, weekday but nonworking)
        with patch('pendulum.now') as mock_now:
            # Wednesday, Jan 8, 2025 08:00 UTC
            mock_now.return_value = pendulum.parse("2025-01-08T08:00:00+00:00")
            
            result = schedule.get_next_working_day("UTC")
            
            # Should return Thursday (Jan 9, 2025) since Wednesday is nonworking
            expected = Date(2025, 1, 9)
            assert result == expected
    
    def test_nonworking_weekday_priority_over_working_weekend(self):
        """Test that nonworking_weekdays has priority over working_weekends"""
        schedule = Schedule(
            name="default",
            start_of_day="09:00:00",
            timezone="UTC",
            weekends=["Sat", "Sun"],
            working_weekends=["2025-01-11"],  # Saturday Jan 11 as working
            nonworking_weekdays=["2025-01-11"]  # Same Saturday as nonworking (vacation)
        )
        
        # Mock current time to Saturday 08:00 (before start_of_day)
        with patch('pendulum.now') as mock_now:
            # Saturday, Jan 11, 2025 08:00 UTC
            mock_now.return_value = pendulum.parse("2025-01-11T08:00:00+00:00")
            
            result = schedule.get_next_working_day("UTC")
            
            # Should return Monday (Jan 13, 2025) since nonworking has priority
            expected = Date(2025, 1, 13)
            assert result == expected
    
    def test_multiple_consecutive_nonworking_days(self):
        """Test multiple consecutive nonworking days"""
        schedule = Schedule(
            name="default",
            start_of_day="09:00:00",
            timezone="UTC",
            weekends=["Sat", "Sun"],
            nonworking_weekdays=["2025-01-08", "2025-01-10"]  # Wed Jan 8 and Fri Jan 10
        )
        
        # Mock current time to Wednesday 08:00 (before start_of_day)
        with patch('pendulum.now') as mock_now:
            # Wednesday, Jan 8, 2025 08:00 UTC
            mock_now.return_value = pendulum.parse("2025-01-08T08:00:00+00:00")
            
            result = schedule.get_next_working_day("UTC")
            
            # Should return Thursday (Jan 9, 2025), skipping Wed (nonworking) and Fri (nonworking)
            expected = Date(2025, 1, 9)
            assert result == expected
    
    def test_nonworking_weekday_range(self):
        """Test nonworking weekday specified as a range"""
        schedule = Schedule(
            name="default",
            start_of_day="09:00:00",
            timezone="UTC",
            weekends=["Sat", "Sun"],
            nonworking_weekdays=[["2025-01-08", "2025-01-10"]]  # Range Wed-Fri
        )
        
        # Mock current time to Thursday 08:00 (before start_of_day, in nonworking range)
        with patch('pendulum.now') as mock_now:
            # Thursday, Jan 9, 2025 08:00 UTC
            mock_now.return_value = pendulum.parse("2025-01-09T08:00:00+00:00")
            
            result = schedule.get_next_working_day("UTC")
            
            # Should return Monday (Jan 13, 2025), skipping Thu/Fri (nonworking range) and weekend
            expected = Date(2025, 1, 13)
            assert result == expected
    
    def test_timezone_handling(self):
        """Test that timezone is handled correctly"""
        schedule = Schedule(
            name="default",
            start_of_day="09:00:00",
            timezone="America/New_York",
            weekends=["Sat", "Sun"]
        )
        
        # Mock current time to 08:00 in New York (before start_of_day in local time)
        with patch('pendulum.now') as mock_now:
            # Wednesday, Jan 8, 2025 08:00 EST
            mock_now.return_value = pendulum.parse("2025-01-08T08:00:00-05:00")
            
            result = schedule.get_next_working_day("America/New_York")
            
            # Should return today since it's before start_of_day in the specified timezone
            expected = Date(2025, 1, 8)
            assert result == expected
    
    def test_auto_timezone(self):
        """Test auto timezone detection"""
        schedule = Schedule(
            name="default",
            start_of_day="09:00:00",
            timezone="UTC",
            weekends=["Sat", "Sun"]
        )
        
        with patch('pendulum.now') as mock_now, \
             patch('pendulum.local_timezone') as mock_local_tz:
            
            # Mock local timezone as UTC
            mock_local_tz.return_value = pendulum.timezone("UTC")
            # Wednesday, Jan 8, 2025 08:00 UTC (before start_of_day)
            mock_now.return_value = pendulum.parse("2025-01-08T08:00:00+00:00")
            
            result = schedule.get_next_working_day("auto")
            
            # Should return today
            expected = Date(2025, 1, 8)
            assert result == expected
    
    def test_complex_scenario_weekend_to_next_weekday(self):
        """Test complex scenario: weekend -> nonworking Monday -> working Tuesday"""
        schedule = Schedule(
            name="default",
            start_of_day="09:00:00",
            timezone="UTC",
            weekends=["Sat", "Sun"],
            nonworking_weekdays=["2025-01-13"]  # Monday Jan 13
        )
        
        # Mock current time to Sunday 10:00 (after start_of_day, weekend)
        with patch('pendulum.now') as mock_now:
            # Sunday, Jan 12, 2025 10:00 UTC
            mock_now.return_value = pendulum.parse("2025-01-12T10:00:00+00:00")
            
            result = schedule.get_next_working_day("UTC")
            
            # Should return Tuesday (Jan 14, 2025), skipping Monday (nonworking)
            expected = Date(2025, 1, 14)
            assert result == expected


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
