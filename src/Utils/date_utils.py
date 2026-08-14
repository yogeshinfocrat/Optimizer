# A utility file for date related functions

from datetime import datetime, timedelta
from dateutil import parser


def get_minutes_from_string(time_string: str) -> int:
    """
    Converts a time string to minutes from midnight.
    Format is expected to be HH:MM:SS
    """
    time = parser.parse(time_string)
    return time.hour * 60 + time.minute


def get_datetime_from_day_and_time(day: str, time: str) -> datetime:
    """
    Converts a day and time string to a datetime object.
    Format is expected to be MM/DD/YYYY and HH:MM
    """
    day = parser.parse(day)
    time = parser.parse(time)
    return datetime.combine(day, time.time())


def get_date_and_time_from_minutes(minutes: int, start_date) -> tuple[str, str, str]:
    """
    Converts minutes from midnight to a date and time string.
    Format is expected to be MM/DD/YYYY and HH:MM
    """
    # start_date: datetime = parser.parse(start_date)
    start_date = datetime.combine(start_date, datetime.min.time())
    start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    time = start_date + timedelta(minutes=minutes)

    # Get day of the week in format of "monday", "tuesday", etc.
    day = get_day_of_week_string(time)

    return time.strftime("%m/%d/%Y"), time.strftime("%H:%M"), day


def get_day_of_week_string(date: datetime) -> str:
    """Returns the day of the week in lowercase"""
    return date.strftime("%A").lower()


def is_date_in_range(date: datetime, start_date: datetime, end_date: datetime) -> bool:
    """Returns true if the date is in the range of the start and end date"""
    return start_date <= date <= end_date


def get_minutes_from_date_time(date: datetime) -> int:
    """Returns the number of minutes from midnight"""
    return date.hour * 60 + date.minute


def get_days_from_value(value):
    DAYS_OF_WEEK = {
        1: "su",  # 2^0
        2: "mo",  # 2^1
        4: "tu",  # 2^2
        8: "we",  # 2^3
        16: "thu",  # 2^4
        32: "fri",  # 2^5
        64: "sat"  # 2^6
    }
    """
    Function to determine which days are included in the given value.

    Parameters:
    value (int): The integer representing the combination of days.

    Returns:
    tuple: A list of included day names.
    """
    days_included = []  # List to store the names of included days
    # Iterate through the keys (values) in the DAYS_OF_WEEK dictionary
    for key in DAYS_OF_WEEK.keys():
        # Check if the bit corresponding to the current key is set in the value
        if value & key:  # Bitwise AND operation
            days_included.append(key)  # Add the day name to the list


    return [DAYS_OF_WEEK[i] for i in days_included]  # Return the list of days