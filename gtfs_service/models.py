from sqlalchemy import Column, String, Integer, Float, Boolean, Date, Time, Index
from gtfs_service.database import Base


class Agency(Base):
    __tablename__ = "agency"
    id = Column(Integer, primary_key=True, autoincrement=True)
    agency_id = Column(String, index=True)
    agency_name = Column(String, nullable=False)
    agency_url = Column(String)
    agency_timezone = Column(String, nullable=False)
    agency_lang = Column(String)
    agency_phone = Column(String)


class Stop(Base):
    __tablename__ = "stops"
    id = Column(Integer, primary_key=True, autoincrement=True)
    stop_id = Column(String, unique=True, index=True, nullable=False)
    stop_code = Column(String)
    stop_name = Column(String, nullable=False)
    stop_desc = Column(String)
    stop_lat = Column(Float, nullable=False)
    stop_lon = Column(Float, nullable=False)
    zone_id = Column(String)
    stop_url = Column(String)
    location_type = Column(Integer, default=0)
    parent_station = Column(String)
    wheelchair_boarding = Column(Integer)

    __table_args__ = (
        Index('idx_stop_coords', 'stop_lat', 'stop_lon'),
    )


class Route(Base):
    __tablename__ = "routes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    route_id = Column(String, unique=True, index=True, nullable=False)
    agency_id = Column(String)
    route_short_name = Column(String)
    route_long_name = Column(String)
    route_desc = Column(String)
    route_type = Column(Integer, nullable=False)
    route_url = Column(String)
    route_color = Column(String)
    route_text_color = Column(String)


class Trip(Base):
    __tablename__ = "trips"
    id = Column(Integer, primary_key=True, autoincrement=True)
    route_id = Column(String, index=True, nullable=False)
    service_id = Column(String, index=True, nullable=False)
    trip_id = Column(String, unique=True, index=True, nullable=False)
    trip_headsign = Column(String)
    trip_short_name = Column(String)
    direction_id = Column(Integer, default=0)
    block_id = Column(String)
    shape_id = Column(String)
    wheelchair_accessible = Column(Integer)
    bikes_allowed = Column(Integer)

    __table_args__ = (
        Index('idx_route_service', 'route_id', 'service_id'),
    )


class StopTime(Base):
    __tablename__ = "stop_times"
    id = Column(Integer, primary_key=True, autoincrement=True)
    trip_id = Column(String, index=True, nullable=False)
    arrival_time = Column(String, nullable=False)
    departure_time = Column(String, nullable=False)
    stop_id = Column(String, index=True, nullable=False)
    stop_sequence = Column(Integer, nullable=False)
    stop_headsign = Column(String)
    pickup_type = Column(Integer, default=0)
    drop_off_type = Column(Integer, default=0)
    shape_dist_traveled = Column(Float)

    __table_args__ = (
        Index('idx_trip_stop', 'trip_id', 'stop_sequence'),
        Index('idx_stop_time', 'stop_id', 'departure_time'),
    )


class Calendar(Base):
    __tablename__ = "calendar"
    id = Column(Integer, primary_key=True, autoincrement=True)
    service_id = Column(String, unique=True, index=True, nullable=False)
    monday = Column(Boolean, nullable=False)
    tuesday = Column(Boolean, nullable=False)
    wednesday = Column(Boolean, nullable=False)
    thursday = Column(Boolean, nullable=False)
    friday = Column(Boolean, nullable=False)
    saturday = Column(Boolean, nullable=False)
    sunday = Column(Boolean, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)


class CalendarDate(Base):
    __tablename__ = "calendar_dates"
    id = Column(Integer, primary_key=True, autoincrement=True)
    service_id = Column(String, index=True, nullable=False)
    date = Column(Date, nullable=False, index=True)
    exception_type = Column(Integer, nullable=False)


class Shape(Base):
    __tablename__ = "shapes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    shape_id = Column(String, index=True, nullable=False)
    shape_pt_lat = Column(Float, nullable=False)
    shape_pt_lon = Column(Float, nullable=False)
    shape_pt_sequence = Column(Integer, nullable=False)
    shape_dist_traveled = Column(Float)


class RealTimeDelay(Base):
    __tablename__ = "real_time_delays"
    id = Column(Integer, primary_key=True, autoincrement=True)
    trip_id = Column(String, index=True, nullable=False)
    stop_id = Column(String, index=True)
    delay_seconds = Column(Integer, nullable=False, default=0)
    timestamp = Column(Integer, nullable=False)
    active = Column(Boolean, default=True)
