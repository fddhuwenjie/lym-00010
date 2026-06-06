from typing import List, Dict, Set, Tuple, Optional
from sqlalchemy.orm import Session
from geopy.distance import geodesic

from gtfs_service.models import (
    Stop, Route, Trip, StopTime, Calendar, CalendarDate, Shape
)
from gtfs_service.schemas import ValidationError, ValidationResponse
from gtfs_service.utils import time_to_seconds, seconds_to_time


class GTFSValidator:
    def __init__(self, db: Session):
        self.db = db
        self.errors: List[ValidationError] = []

    def validate(self) -> ValidationResponse:
        self.errors = []

        self._validate_stops()
        self._validate_routes()
        self._validate_trips()
        self._validate_stop_times()
        self._validate_calendar()
        self._validate_shapes()
        self._validate_references()

        return ValidationResponse(
            total_errors=len(self.errors),
            errors=self.errors
        )

    def _add_error(self, error_type: str, message: str, entity_id: Optional[str] = None, details: Optional[Dict] = None):
        self.errors.append(ValidationError(
            error_type=error_type,
            message=message,
            entity_id=entity_id,
            details=details or {}
        ))

    def _validate_stops(self):
        stops = self.db.query(Stop).all()
        stop_ids = set()

        for stop in stops:
            if stop.stop_id in stop_ids:
                self._add_error(
                    'duplicate_stop_id',
                    f"Duplicate stop_id: {stop.stop_id}",
                    stop.stop_id
                )
            stop_ids.add(stop.stop_id)

            if stop.stop_lat < -90 or stop.stop_lat > 90:
                self._add_error(
                    'invalid_coordinates',
                    f"Invalid latitude for stop {stop.stop_id}: {stop.stop_lat}",
                    stop.stop_id,
                    {'latitude': stop.stop_lat}
                )

            if stop.stop_lon < -180 or stop.stop_lon > 180:
                self._add_error(
                    'invalid_coordinates',
                    f"Invalid longitude for stop {stop.stop_id}: {stop.stop_lon}",
                    stop.stop_id,
                    {'longitude': stop.stop_lon}
                )

            if not stop.stop_name or len(stop.stop_name.strip()) == 0:
                self._add_error(
                    'missing_stop_name',
                    f"Stop {stop.stop_id} has no name",
                    stop.stop_id
                )

    def _validate_routes(self):
        routes = self.db.query(Route).all()
        route_ids = set()

        for route in routes:
            if route.route_id in route_ids:
                self._add_error(
                    'duplicate_route_id',
                    f"Duplicate route_id: {route.route_id}",
                    route.route_id
                )
            route_ids.add(route.route_id)

            if route.route_type not in [0, 1, 2, 3, 4, 5, 6, 7, 11, 12]:
                self._add_error(
                    'invalid_route_type',
                    f"Invalid route_type for route {route.route_id}: {route.route_type}",
                    route.route_id,
                    {'route_type': route.route_type}
                )

            if not route.route_short_name and not route.route_long_name:
                self._add_error(
                    'missing_route_name',
                    f"Route {route.route_id} has no short or long name",
                    route.route_id
                )

    def _validate_trips(self):
        trips = self.db.query(Trip).all()
        trip_ids = set()

        route_ids = {r.route_id for r in self.db.query(Route).all()}
        service_ids = {s.service_id for s in self.db.query(Calendar).all()}
        service_ids.update({s.service_id for s in self.db.query(CalendarDate).all()})

        for trip in trips:
            if trip.trip_id in trip_ids:
                self._add_error(
                    'duplicate_trip_id',
                    f"Duplicate trip_id: {trip.trip_id}",
                    trip.trip_id
                )
            trip_ids.add(trip.trip_id)

            if trip.route_id not in route_ids:
                self._add_error(
                    'missing_route_reference',
                    f"Trip {trip.trip_id} references non-existent route {trip.route_id}",
                    trip.trip_id,
                    {'route_id': trip.route_id}
                )

            if trip.service_id not in service_ids:
                self._add_error(
                    'missing_service_reference',
                    f"Trip {trip.trip_id} references non-existent service {trip.service_id}",
                    trip.trip_id,
                    {'service_id': trip.service_id}
                )

    def _validate_stop_times(self):
        stop_times = self.db.query(StopTime).order_by(
            StopTime.trip_id, StopTime.stop_sequence
        ).all()

        stop_ids = {s.stop_id for s in self.db.query(Stop).all()}
        trip_ids = {t.trip_id for t in self.db.query(Trip).all()}

        trip_stop_times: Dict[str, List[StopTime]] = {}
        for st in stop_times:
            if st.trip_id not in trip_stop_times:
                trip_stop_times[st.trip_id] = []
            trip_stop_times[st.trip_id].append(st)

            if st.trip_id not in trip_ids:
                self._add_error(
                    'missing_trip_reference',
                    f"Stop_time references non-existent trip {st.trip_id}",
                    st.trip_id
                )

            if st.stop_id not in stop_ids:
                self._add_error(
                    'missing_stop_reference',
                    f"Stop_time references non-existent stop {st.stop_id}",
                    st.stop_id,
                    {'trip_id': st.trip_id, 'stop_id': st.stop_id}
                )

        for trip_id, st_list in trip_stop_times.items():
            sequences = [st.stop_sequence for st in st_list]
            if len(sequences) != len(set(sequences)):
                self._add_error(
                    'duplicate_stop_sequence',
                    f"Trip {trip_id} has duplicate stop sequences",
                    trip_id
                )

            if sequences != sorted(sequences):
                self._add_error(
                    'stop_sequence_not_sorted',
                    f"Trip {trip_id} stop sequences are not in order",
                    trip_id
                )

            prev_dep = None
            for i, st in enumerate(st_list):
                try:
                    arr_secs = time_to_seconds(st.arrival_time)
                    dep_secs = time_to_seconds(st.departure_time)
                except:
                    self._add_error(
                        'invalid_time_format',
                        f"Invalid time format in trip {trip_id} at sequence {st.stop_sequence}",
                        trip_id,
                        {'arrival_time': st.arrival_time, 'departure_time': st.departure_time}
                    )
                    continue

                if arr_secs > dep_secs:
                    self._add_error(
                        'time_reversed',
                        f"Arrival time after departure time in trip {trip_id} at stop {st.stop_id}",
                        trip_id,
                        {'stop_id': st.stop_id, 'arrival': st.arrival_time, 'departure': st.departure_time}
                    )

                if prev_dep is not None and arr_secs < prev_dep:
                    self._add_error(
                        'time_not_monotonic',
                        f"Time travel detected in trip {trip_id}: arrives at stop {st.stop_id} before departing previous stop",
                        trip_id,
                        {'stop_id': st.stop_id, 'arrival': st.arrival_time, 'prev_departure': seconds_to_time(prev_dep) if prev_dep else 'N/A'}
                    )

                prev_dep = dep_secs

            if len(st_list) < 2:
                self._add_error(
                    'insufficient_stops',
                    f"Trip {trip_id} has fewer than 2 stops",
                    trip_id,
                    {'stop_count': len(st_list)}
                )

    def _validate_calendar(self):
        calendars = self.db.query(Calendar).all()

        for cal in calendars:
            if cal.start_date > cal.end_date:
                self._add_error(
                    'date_range_inverted',
                    f"Service {cal.service_id} has start_date after end_date",
                    cal.service_id,
                    {'start_date': str(cal.start_date), 'end_date': str(cal.end_date)}
                )

            has_service = any([
                cal.monday, cal.tuesday, cal.wednesday, cal.thursday,
                cal.friday, cal.saturday, cal.sunday
            ])
            if not has_service:
                self._add_error(
                    'no_service_days',
                    f"Service {cal.service_id} has no days of week enabled",
                    cal.service_id
                )

        calendar_dates = self.db.query(CalendarDate).all()
        for cd in calendar_dates:
            if cd.exception_type not in [1, 2]:
                self._add_error(
                    'invalid_exception_type',
                    f"Calendar date for service {cd.service_id} has invalid exception_type {cd.exception_type}",
                    cd.service_id,
                    {'date': str(cd.date), 'exception_type': cd.exception_type}
                )

    def _validate_shapes(self):
        shapes = self.db.query(Shape).order_by(
            Shape.shape_id, Shape.shape_pt_sequence
        ).all()

        shape_points: Dict[str, List[Shape]] = {}
        for s in shapes:
            if s.shape_id not in shape_points:
                shape_points[s.shape_id] = []
            shape_points[s.shape_id].append(s)

        trips_with_shapes = self.db.query(Trip).filter(Trip.shape_id.isnot(None)).all()
        shape_ids_with_trips = {t.shape_id for t in trips_with_shapes}

        for shape_id, points in shape_points.items():
            if shape_id not in shape_ids_with_trips:
                self._add_error(
                    'orphaned_shape',
                    f"Shape {shape_id} is not referenced by any trip",
                    shape_id
                )

            sequences = [p.shape_pt_sequence for p in points]
            if len(sequences) != len(set(sequences)):
                self._add_error(
                    'duplicate_shape_sequence',
                    f"Shape {shape_id} has duplicate point sequences",
                    shape_id
                )

            if sequences != sorted(sequences):
                self._add_error(
                    'shape_sequence_not_sorted',
                    f"Shape {shape_id} point sequences are not in order",
                    shape_id
                )

            for i, p in enumerate(points):
                if p.shape_pt_lat < -90 or p.shape_pt_lat > 90 or p.shape_pt_lon < -180 or p.shape_pt_lon > 180:
                    self._add_error(
                        'invalid_shape_coordinates',
                        f"Shape {shape_id} has invalid coordinates at sequence {p.shape_pt_sequence}",
                        shape_id,
                        {'lat': p.shape_pt_lat, 'lon': p.shape_pt_lon}
                    )

                if i > 0:
                    prev = points[i-1]
                    dist = geodesic(
                        (prev.shape_pt_lat, prev.shape_pt_lon),
                        (p.shape_pt_lat, p.shape_pt_lon)
                    ).meters
                    if dist > 5000:
                        self._add_error(
                            'shape_point_too_far',
                            f"Shape {shape_id} has points more than 5km apart at sequence {p.shape_pt_sequence}",
                            shape_id,
                            {'distance_meters': round(dist, 2)}
                        )

            self._validate_shape_deviation(shape_id, points)

    def _validate_shape_deviation(self, shape_id: str, shape_points: List[Shape]):
        trips = self.db.query(Trip).filter(Trip.shape_id == shape_id).all()

        for trip in trips:
            stop_times = self.db.query(StopTime).filter(
                StopTime.trip_id == trip.trip_id
            ).order_by(StopTime.stop_sequence).all()

            stops = []
            for st in stop_times:
                stop = self.db.query(Stop).filter(Stop.stop_id == st.stop_id).first()
                if stop:
                    stops.append(stop)

            if len(stops) < 2 or len(shape_points) < 2:
                continue

            for stop in stops:
                min_dist = min(
                    geodesic((stop.stop_lat, stop.stop_lon),
                             (sp.shape_pt_lat, sp.shape_pt_lon)).meters
                    for sp in shape_points
                )
                if min_dist > 200:
                    self._add_error(
                        'stop_shape_deviation',
                        f"Stop {stop.stop_id} is {round(min_dist)}m from shape {shape_id}",
                        trip.trip_id,
                        {'stop_id': stop.stop_id, 'distance_meters': round(min_dist, 2)}
                    )

    def _validate_references(self):
        stop_ids = {s.stop_id for s in self.db.query(Stop).all()}
        route_ids = {r.route_id for r in self.db.query(Route).all()}
        trip_ids = {t.trip_id for t in self.db.query(Trip).all()}

        routes_without_trips = route_ids - {t.route_id for t in self.db.query(Trip).all()}
        for route_id in routes_without_trips:
            self._add_error(
                'route_without_trips',
                f"Route {route_id} has no associated trips",
                route_id
            )

        trips_without_stop_times = trip_ids - {st.trip_id for st in self.db.query(StopTime).all()}
        for trip_id in trips_without_stop_times:
            self._add_error(
                'trip_without_stop_times',
                f"Trip {trip_id} has no associated stop_times",
                trip_id
            )

        stops_without_stop_times = stop_ids - {st.stop_id for st in self.db.query(StopTime).all()}
        for stop_id in stops_without_stop_times:
            self._add_error(
                'stop_without_stop_times',
                f"Stop {stop_id} is not served by any trip",
                stop_id
            )
