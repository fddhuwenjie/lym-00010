from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import date, datetime
from typing import List, Optional
from geopy.distance import geodesic

from gtfs_service.database import get_db
from gtfs_service.models import Stop, Route, Trip, StopTime, RealTimeDelay
from gtfs_service.importer import GTFSImporter
from gtfs_service.validator import GTFSValidator
from gtfs_service.pathfinding import TransferFinder
from gtfs_service.utils import (
    get_active_services, time_to_seconds, parse_datetime,
    get_walking_duration
)
from gtfs_service.schemas import (
    StopBase, StopNearby, RouteBase,
    RouteScheduleResponse, ScheduleEntry, StopTimeEntry,
    TransferResponse, DelayInjection, ValidationResponse,
    ImportResponse
)

router = APIRouter()


@router.post("/import", response_model=ImportResponse)
async def import_gtfs(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    try:
        content = await file.read()
        importer = GTFSImporter(db)
        stats = importer.import_gtfs_zip(content)

        return ImportResponse(
            success=True,
            stats=stats,
            message="GTFS data imported successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Import failed: {str(e)}")


@router.get("/stops/nearby", response_model=List[StopNearby])
def get_nearby_stops(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
    radius: float = Query(500, description="Search radius in meters"),
    limit: int = Query(20, description="Max results"),
    db: Session = Depends(get_db)
):
    stops = db.query(Stop).filter(
        Stop.location_type.in_([0, None])
    ).all()

    results = []
    for stop in stops:
        dist = geodesic((lat, lon), (stop.stop_lat, stop.stop_lon)).meters
        if dist <= radius:
            results.append(StopNearby(
                stop_id=stop.stop_id,
                stop_name=stop.stop_name,
                stop_lat=stop.stop_lat,
                stop_lon=stop.stop_lon,
                stop_code=stop.stop_code,
                stop_desc=stop.stop_desc,
                distance=round(dist, 2)
            ))

    results.sort(key=lambda x: x.distance)
    return results[:limit]


@router.get("/stops", response_model=List[StopBase])
def get_all_stops(db: Session = Depends(get_db)):
    stops = db.query(Stop).filter(
        Stop.location_type.in_([0, None])
    ).all()
    return [
        StopBase(
            stop_id=s.stop_id,
            stop_name=s.stop_name,
            stop_lat=s.stop_lat,
            stop_lon=s.stop_lon,
            stop_code=s.stop_code,
            stop_desc=s.stop_desc
        ) for s in stops
    ]


@router.get("/stops/{stop_id}", response_model=StopBase)
def get_stop(stop_id: str, db: Session = Depends(get_db)):
    stop = db.query(Stop).filter(Stop.stop_id == stop_id).first()
    if not stop:
        raise HTTPException(status_code=404, detail="Stop not found")
    return StopBase(
        stop_id=stop.stop_id,
        stop_name=stop.stop_name,
        stop_lat=stop.stop_lat,
        stop_lon=stop.stop_lon,
        stop_code=stop.stop_code,
        stop_desc=stop.stop_desc
    )


@router.get("/stops/{stop_id}/routes", response_model=List[RouteBase])
def get_routes_at_stop(stop_id: str, db: Session = Depends(get_db)):
    stop = db.query(Stop).filter(Stop.stop_id == stop_id).first()
    if not stop:
        raise HTTPException(status_code=404, detail="Stop not found")

    routes = db.query(Route).join(
        Trip, Route.route_id == Trip.route_id
    ).join(
        StopTime, Trip.trip_id == StopTime.trip_id
    ).filter(
        StopTime.stop_id == stop_id
    ).distinct().all()

    return [
        RouteBase(
            route_id=r.route_id,
            route_short_name=r.route_short_name,
            route_long_name=r.route_long_name,
            route_type=r.route_type,
            route_color=r.route_color
        ) for r in routes
    ]


@router.get("/routes", response_model=List[RouteBase])
def get_all_routes(db: Session = Depends(get_db)):
    routes = db.query(Route).all()
    return [
        RouteBase(
            route_id=r.route_id,
            route_short_name=r.route_short_name,
            route_long_name=r.route_long_name,
            route_type=r.route_type,
            route_color=r.route_color
        ) for r in routes
    ]


@router.get("/routes/{route_id}", response_model=RouteBase)
def get_route(route_id: str, db: Session = Depends(get_db)):
    route = db.query(Route).filter(Route.route_id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    return RouteBase(
        route_id=route.route_id,
        route_short_name=route.route_short_name,
        route_long_name=route.route_long_name,
        route_type=route.route_type,
        route_color=route.route_color
    )


@router.get("/routes/{route_id}/schedule", response_model=RouteScheduleResponse)
def get_route_schedule(
    route_id: str,
    target_date: date = Query(..., description="Date in YYYY-MM-DD format"),
    direction_id: int = Query(0, description="Direction ID (0 or 1)"),
    db: Session = Depends(get_db)
):
    route = db.query(Route).filter(Route.route_id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    active_services = get_active_services(db, target_date)
    is_operating = len(active_services) > 0

    trips = db.query(Trip).filter(
        Trip.route_id == route_id,
        Trip.direction_id == direction_id,
        Trip.service_id.in_(active_services)
    ).all()

    schedules = []
    for trip in trips:
        stop_times = db.query(StopTime).filter(
            StopTime.trip_id == trip.trip_id
        ).order_by(StopTime.stop_sequence).all()

        st_entries = []
        for st in stop_times:
            stop = db.query(Stop).filter(Stop.stop_id == st.stop_id).first()
            st_entries.append(StopTimeEntry(
                stop_id=st.stop_id,
                stop_name=stop.stop_name if stop else st.stop_id,
                arrival_time=st.arrival_time,
                departure_time=st.departure_time,
                stop_sequence=st.stop_sequence
            ))

        schedules.append(ScheduleEntry(
            trip_id=trip.trip_id,
            trip_headsign=trip.trip_headsign,
            stop_times=st_entries
        ))

    schedules.sort(key=lambda s: s.stop_times[0].departure_time if s.stop_times else "")

    route_name = route.route_short_name or route.route_long_name
    return RouteScheduleResponse(
        route_id=route_id,
        route_name=route_name,
        direction_id=direction_id,
        date=target_date,
        is_operating=is_operating,
        schedules=schedules
    )


@router.get("/transfers", response_model=TransferResponse)
def get_transfers(
    from_stop_id: str = Query(..., description="Origin stop ID"),
    to_stop_id: str = Query(..., description="Destination stop ID"),
    departure_time: str = Query(..., description="Departure datetime (YYYY-MM-DD HH:MM)"),
    db: Session = Depends(get_db)
):
    try:
        dt = parse_datetime(departure_time)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    from_stop = db.query(Stop).filter(Stop.stop_id == from_stop_id).first()
    to_stop = db.query(Stop).filter(Stop.stop_id == to_stop_id).first()

    if not from_stop:
        raise HTTPException(status_code=404, detail=f"Origin stop {from_stop_id} not found")
    if not to_stop:
        raise HTTPException(status_code=404, detail=f"Destination stop {to_stop_id} not found")

    finder = TransferFinder(db)
    plans = finder.find_transfers(from_stop_id, to_stop_id, dt)

    return TransferResponse(
        from_stop_id=from_stop_id,
        from_stop_name=from_stop.stop_name,
        to_stop_id=to_stop_id,
        to_stop_name=to_stop.stop_name,
        departure_time=departure_time,
        plans=plans
    )


@router.post("/delay", response_model=dict)
def inject_delay(
    delay: DelayInjection,
    db: Session = Depends(get_db)
):
    trip = db.query(Trip).filter(Trip.trip_id == delay.trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    existing = db.query(RealTimeDelay).filter(
        RealTimeDelay.trip_id == delay.trip_id,
        RealTimeDelay.stop_id == delay.stop_id
    ).first()

    if existing:
        existing.delay_seconds = delay.delay_seconds
        existing.timestamp = int(datetime.now().timestamp())
        existing.active = True
    else:
        new_delay = RealTimeDelay(
            trip_id=delay.trip_id,
            stop_id=delay.stop_id,
            delay_seconds=delay.delay_seconds,
            timestamp=int(datetime.now().timestamp()),
            active=True
        )
        db.add(new_delay)

    db.commit()

    return {
        "success": True,
        "trip_id": delay.trip_id,
        "stop_id": delay.stop_id,
        "delay_seconds": delay.delay_seconds,
        "message": f"Delay of {delay.delay_seconds} seconds injected"
    }


@router.delete("/delay", response_model=dict)
def clear_delays(db: Session = Depends(get_db)):
    count = db.query(RealTimeDelay).update({RealTimeDelay.active: False})
    db.commit()
    return {"success": True, "cleared": count, "message": "All delays cleared"}


@router.get("/validate", response_model=ValidationResponse)
def validate_gtfs(db: Session = Depends(get_db)):
    validator = GTFSValidator(db)
    return validator.validate()


@router.get("/status", response_model=dict)
def get_status(db: Session = Depends(get_db)):
    from gtfs_service.models import Agency, Calendar, Shape

    stats = {
        "agencies": db.query(Agency).count(),
        "stops": db.query(Stop).count(),
        "routes": db.query(Route).count(),
        "trips": db.query(Trip).count(),
        "stop_times": db.query(StopTime).count(),
        "calendar_entries": db.query(Calendar).count(),
        "shapes": db.query(Shape).count(),
        "active_delays": db.query(RealTimeDelay).filter(RealTimeDelay.active == True).count(),
    }
    return {"status": "running", "stats": stats}
