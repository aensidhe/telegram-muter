# -*- coding: utf-8 -*-
import pytest
import pendulum
from pendulum import WeekDay, Date
from unittest.mock import patch
from pydantic import ValidationError

from telegram_muter import TimeSettings, Settings, AuthSettings, Schedule, ScheduleManager, GroupSetting


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



if __name__ == "__main__":
    pytest.main([__file__, "-v"])
