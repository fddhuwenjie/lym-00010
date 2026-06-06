import heapq
from datetime import datetime
from typing import List, Dict, Set, Tuple, Optional, Any
from sqlalchemy.orm import Session
from geopy.distance import geodesic

from gtfs_service.models import Stop, Route, Trip, StopTime, RealTimeDelay
from gtfs_service.utils import (
    time_to_seconds, seconds_to_time, get_active_services,
    get_walking_duration, add_seconds_to_time, time_diff_seconds
)
from gtfs_service.schemas import TransferPlan, TransferSegment


MAX_TRANSFERS = 3
MAX_PLANS = 5
WALKING_RADIUS_METERS = 500
TRANSFER_BUFFER_SECONDS = 120


class TransferFinder:
    def __init__(self, db: Session):
        self.db = db
        self.delays: Dict[Tuple[str, Optional[str]], int] = {}
        self._load_delays()

    def _load_delays(self):
        delays = self.db.query(RealTimeDelay).filter(
            RealTimeDelay.active == True
        ).all()
        for d in delays:
            key = (d.trip_id, d.stop_id)
            self.delays[key] = d.delay_seconds

    def _get_delay(self, trip_id: str, stop_id: str) -> int:
        delay = self.delays.get((trip_id, stop_id), 0)
        if delay == 0:
            delay = self.delays.get((trip_id, None), 0)
        return delay

    def _get_stop_by_id(self, stop_id: str) -> Optional[Stop]:
        return self.db.query(Stop).filter(Stop.stop_id == stop_id).first()

    def _get_nearby_stops(self, lat: float, lon: float, radius: float) -> List[Tuple[Stop, float]]:
        stops = self.db.query(Stop).filter(
            Stop.location_type.in_([0, None])
        ).all()

        results = []
        for stop in stops:
            dist = geodesic((lat, lon), (stop.stop_lat, stop.stop_lon)).meters
            if dist <= radius:
                results.append((stop, dist))

        results.sort(key=lambda x: x[1])
        return results

    def _get_routes_at_stop(self, stop_id: str, active_services: Set[str]) -> List[Dict[str, Any]]:
        results = self.db.query(
            Route.route_id,
            Route.route_short_name,
            Route.route_long_name,
            Trip.trip_id,
            Trip.direction_id,
            StopTime.departure_time,
            StopTime.stop_sequence
        ).join(
            Trip, Route.route_id == Trip.route_id
        ).join(
            StopTime, Trip.trip_id == StopTime.trip_id
        ).filter(
            StopTime.stop_id == stop_id,
            Trip.service_id.in_(active_services)
        ).distinct().all()

        route_list = []
        for r in results:
            route_list.append({
                'route_id': r.route_id,
                'route_name': r.route_short_name or r.route_long_name,
                'trip_id': r.trip_id,
                'direction_id': r.direction_id,
                'departure_time': r.departure_time,
                'stop_sequence': r.stop_sequence
            })
        return route_list

    def _get_trip_stops(self, trip_id: str) -> List[StopTime]:
        return self.db.query(StopTime).filter(
            StopTime.trip_id == trip_id
        ).order_by(StopTime.stop_sequence).all()

    def _get_stop_name(self, stop_id: str) -> str:
        stop = self._get_stop_by_id(stop_id)
        return stop.stop_name if stop else stop_id

    def find_transfers(
        self,
        from_stop_id: str,
        to_stop_id: str,
        departure_datetime: datetime
    ) -> List[TransferPlan]:
        from_stop = self._get_stop_by_id(from_stop_id)
        to_stop = self._get_stop_by_id(to_stop_id)

        if not from_stop or not to_stop:
            return []

        active_services = get_active_services(self.db, departure_datetime.date())
        departure_secs = departure_datetime.hour * 3600 + departure_datetime.minute * 60

        walk_time = get_walking_duration(
            from_stop.stop_lat, from_stop.stop_lon,
            to_stop.stop_lat, to_stop.stop_lon
        )

        if walk_time <= 900:
            walk_plan = self._create_walk_plan(from_stop, to_stop, departure_secs)
            initial_plans = [walk_plan]
        else:
            initial_plans = []

        plans = self._dijkstra_search(
            from_stop, to_stop, departure_secs, active_services
        )

        all_plans = initial_plans + plans
        all_plans.sort(key=lambda p: (p.transfers, p.total_duration_seconds))
        return all_plans[:MAX_PLANS]

    def _create_walk_plan(self, from_stop: Stop, to_stop: Stop, departure_secs: int) -> TransferPlan:
        walk_time = get_walking_duration(
            from_stop.stop_lat, from_stop.stop_lon,
            to_stop.stop_lat, to_stop.stop_lon
        )

        segment = TransferSegment(
            type='walk',
            from_stop_id=from_stop.stop_id,
            from_stop_name=from_stop.stop_name,
            to_stop_id=to_stop.stop_id,
            to_stop_name=to_stop.stop_name,
            duration_seconds=walk_time
        )

        return TransferPlan(
            total_duration_seconds=walk_time,
            total_walking_seconds=walk_time,
            transfers=0,
            segments=[segment],
            score=walk_time * 2.0
        )

    def _dijkstra_search(
        self,
        from_stop: Stop,
        to_stop: Stop,
        departure_secs: int,
        active_services: Set[str]
    ) -> List[TransferPlan]:
        heap = []
        visited = {}
        plans: List[TransferPlan] = []

        start_state = (departure_secs, from_stop.stop_id, 0, [], set([from_stop.stop_id]))
        heapq.heappush(heap, (0, id(start_state), start_state))

        stop_routes_cache: Dict[str, List] = {}

        while heap and len(plans) < MAX_PLANS * 3:
            cost, _, state = heapq.heappop(heap)
            current_time, current_stop_id, transfers, path, visited_stops = state

            state_key = (current_stop_id, transfers)
            if state_key in visited and visited[state_key] <= current_time:
                continue
            visited[state_key] = current_time

            if current_stop_id == to_stop.stop_id and path:
                plan = self._path_to_plan(path, from_stop, to_stop, departure_secs)
                if plan:
                    plans.append(plan)
                continue

            if transfers > MAX_TRANSFERS:
                continue

            if current_stop_id not in stop_routes_cache:
                stop_routes_cache[current_stop_id] = self._get_routes_at_stop(
                    current_stop_id, active_services
                )

            routes_at_stop = stop_routes_cache[current_stop_id]

            for route_info in routes_at_stop:
                route_dep_secs = time_to_seconds(route_info['departure_time'])
                if route_dep_secs < current_time:
                    continue

                delay = self._get_delay(route_info['trip_id'], current_stop_id)
                actual_dep_secs = route_dep_secs + delay
                if actual_dep_secs < current_time:
                    continue

                trip_stops = self._get_trip_stops(route_info['trip_id'])
                current_seq = route_info['stop_sequence']

                for st in trip_stops:
                    if st.stop_sequence <= current_seq:
                        continue

                    if st.stop_id in visited_stops:
                        continue

                    arr_delay = self._get_delay(route_info['trip_id'], st.stop_id)
                    actual_arr_secs = time_to_seconds(st.arrival_time) + arr_delay

                    transfer_bonus = 0
                    if transfers > 0:
                        if actual_dep_secs - current_time < TRANSFER_BUFFER_SECONDS:
                            transfer_bonus = 600

                    new_path = path + [{
                        'type': 'ride',
                        'route_id': route_info['route_id'],
                        'route_name': route_info['route_name'],
                        'trip_id': route_info['trip_id'],
                        'from_stop_id': current_stop_id,
                        'from_stop_name': self._get_stop_name(current_stop_id),
                        'to_stop_id': st.stop_id,
                        'to_stop_name': self._get_stop_name(st.stop_id),
                        'departure_time': seconds_to_time(actual_dep_secs),
                        'arrival_time': seconds_to_time(actual_arr_secs),
                        'departure_secs': actual_dep_secs,
                        'arrival_secs': actual_arr_secs,
                    }]

                    new_visited = visited_stops.copy()
                    new_visited.add(st.stop_id)
                    new_cost = cost + (actual_arr_secs - departure_secs) + transfer_bonus
                    new_state = (
                        actual_arr_secs + TRANSFER_BUFFER_SECONDS,
                        st.stop_id,
                        transfers + 1,
                        new_path,
                        new_visited
                    )

                    heapq.heappush(heap, (new_cost, id(new_state), new_state))

            nearby = self._get_nearby_stops(
                self._get_stop_by_id(current_stop_id).stop_lat,
                self._get_stop_by_id(current_stop_id).stop_lon,
                WALKING_RADIUS_METERS
            )

            for nb_stop, dist in nearby:
                if nb_stop.stop_id == current_stop_id:
                    continue

                if nb_stop.stop_id in visited_stops:
                    continue

                walk_dur = get_walking_duration(
                    self._get_stop_by_id(current_stop_id).stop_lat,
                    self._get_stop_by_id(current_stop_id).stop_lon,
                    nb_stop.stop_lat,
                    nb_stop.stop_lon
                )
                new_time = current_time + walk_dur

                new_path = path + [{
                    'type': 'walk',
                    'from_stop_id': current_stop_id,
                    'from_stop_name': self._get_stop_name(current_stop_id),
                    'to_stop_id': nb_stop.stop_id,
                    'to_stop_name': nb_stop.stop_name,
                    'departure_secs': current_time,
                    'arrival_secs': new_time,
                    'duration_seconds': walk_dur,
                }]

                new_visited = visited_stops.copy()
                new_visited.add(nb_stop.stop_id)
                new_cost = cost + walk_dur * 1.5
                new_state = (new_time, nb_stop.stop_id, transfers, new_path, new_visited)

                heapq.heappush(heap, (new_cost, id(new_state), new_state))

        return self._deduplicate_plans(plans)

    def _path_to_plan(self, path: List[Dict], from_stop: Stop, to_stop: Stop, departure_secs: int) -> Optional[TransferPlan]:
        if not path:
            return None

        segments = []
        total_walk = 0
        transfers = 0

        for i, leg in enumerate(path):
            if leg['type'] == 'walk':
                seg = TransferSegment(
                    type='walk',
                    from_stop_id=leg['from_stop_id'],
                    from_stop_name=leg['from_stop_name'],
                    to_stop_id=leg['to_stop_id'],
                    to_stop_name=leg['to_stop_name'],
                    duration_seconds=leg['duration_seconds']
                )
                total_walk += leg['duration_seconds']
            else:
                seg = TransferSegment(
                    type='ride',
                    from_stop_id=leg['from_stop_id'],
                    from_stop_name=leg['from_stop_name'],
                    to_stop_id=leg['to_stop_id'],
                    to_stop_name=leg['to_stop_name'],
                    route_id=leg['route_id'],
                    route_name=leg['route_name'],
                    trip_id=leg['trip_id'],
                    departure_time=leg['departure_time'],
                    arrival_time=leg['arrival_time'],
                    duration_seconds=leg['arrival_secs'] - leg['departure_secs']
                )
                if i > 0 and path[i-1]['type'] != 'ride':
                    transfers += 1
                elif i > 0 and path[i-1]['type'] == 'ride' and path[i-1]['route_id'] != leg['route_id']:
                    transfers += 1

            segments.append(seg)

        if not segments:
            return None

        final_time = path[-1]['arrival_secs']
        total_dur = final_time - departure_secs

        score = total_dur + (transfers * 300) + (total_walk * 0.5)

        return TransferPlan(
            total_duration_seconds=total_dur,
            total_walking_seconds=total_walk,
            transfers=transfers,
            segments=segments,
            score=score
        )

    def _deduplicate_plans(self, plans: List[TransferPlan]) -> List[TransferPlan]:
        seen = set()
        unique = []

        for plan in plans:
            key_parts = []
            for seg in plan.segments:
                if seg.type == 'ride':
                    key_parts.append(f"R:{seg.route_id}")
                else:
                    key_parts.append(f"W:{seg.to_stop_id}")
            key = '|'.join(key_parts)

            if key not in seen:
                seen.add(key)
                unique.append(plan)

        return unique
