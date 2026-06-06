from pydantic import BaseModel, Field
from datetime import date, datetime
from typing import List, Optional, Dict, Any


class StopBase(BaseModel):
    stop_id: str
    stop_name: str
    stop_lat: float
    stop_lon: float
    stop_code: Optional[str] = None
    stop_desc: Optional[str] = None


class StopNearby(StopBase):
    distance: float


class RouteBase(BaseModel):
    route_id: str
    route_short_name: str
    route_long_name: str
    route_type: int
    route_color: Optional[str] = None


class TripBase(BaseModel):
    trip_id: str
    trip_headsign: Optional[str] = None
    direction_id: int


class StopTimeEntry(BaseModel):
    stop_id: str
    stop_name: str
    arrival_time: str
    departure_time: str
    stop_sequence: int


class ScheduleEntry(BaseModel):
    trip_id: str
    trip_headsign: Optional[str]
    stop_times: List[StopTimeEntry]


class RouteScheduleResponse(BaseModel):
    route_id: str
    route_name: str
    direction_id: int
    date: date
    is_operating: bool
    schedules: List[ScheduleEntry]


class TransferSegment(BaseModel):
    type: str
    from_stop_id: str
    from_stop_name: str
    to_stop_id: str
    to_stop_name: str
    route_id: Optional[str] = None
    route_name: Optional[str] = None
    trip_id: Optional[str] = None
    departure_time: Optional[str] = None
    arrival_time: Optional[str] = None
    duration_seconds: int


class TransferPlan(BaseModel):
    total_duration_seconds: int
    total_walking_seconds: int
    total_waiting_seconds: int
    total_riding_seconds: int
    transfers: int
    segments: List[TransferSegment]
    score: float


class TransferResponse(BaseModel):
    from_stop_id: str
    from_stop_name: str
    to_stop_id: str
    to_stop_name: str
    departure_time: str
    plans: List[TransferPlan]


class DelayInjection(BaseModel):
    trip_id: str
    stop_id: Optional[str] = None
    delay_seconds: int


class ValidationError(BaseModel):
    error_type: str
    message: str
    entity_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class ValidationResponse(BaseModel):
    total_errors: int
    errors: List[ValidationError]


class ImportResponse(BaseModel):
    success: bool
    stats: Dict[str, int]
    message: str
