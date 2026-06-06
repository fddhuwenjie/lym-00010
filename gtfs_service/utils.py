from datetime import datetime, date, timedelta
from typing import Set, Optional
from sqlalchemy.orm import Session
from gtfs_service.models import Calendar, CalendarDate


WEEKDAY_MAP = {
    0: 'monday',
    1: 'tuesday',
    2: 'wednesday',
    3: 'thursday',
    4: 'friday',
    5: 'saturday',
    6: 'sunday',
}


def time_to_seconds(time_str: str) -> int:
    parts = time_str.split(':')
    if len(parts) == 3:
        h, m, s = map(int, parts)
        return h * 3600 + m * 60 + s
    return 0


def seconds_to_time(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def add_seconds_to_time(time_str: str, add_seconds: int) -> str:
    total = time_to_seconds(time_str) + add_seconds
    return seconds_to_time(total)


def time_diff_seconds(time1: str, time2: str) -> int:
    return time_to_seconds(time2) - time_to_seconds(time1)


def get_active_services(db: Session, target_date: date) -> Set[str]:
    active_services: Set[str] = set()

    weekday = target_date.weekday()
    weekday_field = WEEKDAY_MAP[weekday]

    calendars = db.query(Calendar).filter(
        Calendar.start_date <= target_date,
        Calendar.end_date >= target_date
    ).all()

    for cal in calendars:
        if getattr(cal, weekday_field):
            active_services.add(cal.service_id)

    exceptions = db.query(CalendarDate).filter(
        CalendarDate.date == target_date
    ).all()

    for exc in exceptions:
        if exc.exception_type == 1:
            active_services.add(exc.service_id)
        elif exc.exception_type == 2:
            active_services.discard(exc.service_id)

    return active_services


def is_service_active(db: Session, service_id: str, target_date: date) -> bool:
    return service_id in get_active_services(db, target_date)


def get_walking_duration(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    from geopy.distance import geodesic

    distance_meters = geodesic((lat1, lon1), (lat2, lon2)).meters
    walking_speed_mps = 1.4
    duration_seconds = int(distance_meters / walking_speed_mps)

    min_walk = 60
    return max(min_walk, duration_seconds)


def parse_datetime(datetime_str: str) -> datetime:
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(datetime_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unable to parse datetime: {datetime_str}")
