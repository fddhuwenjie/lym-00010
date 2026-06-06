import csv
import os
import zipfile
from datetime import date, timedelta

BASE_LAT = 31.2304
BASE_LON = 121.4737

GRID_STEP = 0.008


def generate_stops():
    stops = []
    grid = {}
    stop_idx = 1

    row_names = ['Central', 'Downtown', 'Riverside', 'Business', 'University', 'Suburb']
    col_names = ['East', 'South', 'West', 'North', 'Mid', 'New']
    for row in range(6):
        for col in range(6):
            stop_id = f"S{stop_idx:03d}"
            lat = BASE_LAT + row * GRID_STEP
            lon = BASE_LON + col * GRID_STEP
            name = f"{row_names[row]} {col_names[col]} Station"
            grid[(row, col)] = stop_id
            stops.append({
                'stop_id': stop_id,
                'stop_name': name,
                'stop_lat': lat,
                'stop_lon': lon,
                'location_type': 0
            })
            stop_idx += 1
    return stops, grid


def generate_routes():
    return [
        {'route_id': 'R001', 'route_short_name': '1路', 'route_long_name': '东西干线', 'route_type': 3, 'route_color': 'FF0000'},
        {'route_id': 'R002', 'route_short_name': '2路', 'route_long_name': '南北干线', 'route_type': 3, 'route_color': '00FF00'},
        {'route_id': 'R003', 'route_short_name': '3路', 'route_long_name': '对角线', 'route_type': 3, 'route_color': '0000FF'},
        {'route_id': 'R004', 'route_short_name': '4路', 'route_long_name': '环线', 'route_type': 3, 'route_color': 'FF00FF'},
        {'route_id': 'R005', 'route_short_name': '5路', 'route_long_name': '市郊线', 'route_type': 3, 'route_color': 'FFFF00'},
    ]


def generate_calendar():
    today = date.today()
    start_date = today - timedelta(days=30)
    end_date = today + timedelta(days=180)
    return [{
        'service_id': 'WEEKDAY',
        'monday': 1, 'tuesday': 1, 'wednesday': 1, 'thursday': 1, 'friday': 1,
        'saturday': 0, 'sunday': 0,
        'start_date': start_date.strftime('%Y%m%d'),
        'end_date': end_date.strftime('%Y%m%d')
    }, {
        'service_id': 'WEEKEND',
        'monday': 0, 'tuesday': 0, 'wednesday': 0, 'thursday': 0, 'friday': 0,
        'saturday': 1, 'sunday': 1,
        'start_date': start_date.strftime('%Y%m%d'),
        'end_date': end_date.strftime('%Y%m%d')
    }]


def generate_calendar_dates():
    today = date.today()
    next_holiday = today + timedelta(days=(10 - today.weekday() + 7) % 7)
    return [{
        'service_id': 'WEEKDAY',
        'date': next_holiday.strftime('%Y%m%d'),
        'exception_type': 2
    }, {
        'service_id': 'WEEKEND',
        'date': next_holiday.strftime('%Y%m%d'),
        'exception_type': 1
    }]


def generate_trips_and_stop_times(grid):
    trips = []
    stop_times = []
    trip_idx = 1

    route_patterns = [
        ('R001', 'WEEKDAY', 0, [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (0, 5)], 8, 6, 'shp_001'),
        ('R001', 'WEEKDAY', 1, [(0, 5), (0, 4), (0, 3), (0, 2), (0, 1), (0, 0)], 8, 6, 'shp_001'),
        ('R001', 'WEEKEND', 0, [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (0, 5)], 6, 8, 'shp_001'),
        ('R001', 'WEEKEND', 1, [(0, 5), (0, 4), (0, 3), (0, 2), (0, 1), (0, 0)], 6, 8, 'shp_001'),
        ('R002', 'WEEKDAY', 0, [(0, 2), (1, 2), (2, 2), (3, 2), (4, 2), (5, 2)], 8, 6, 'shp_002'),
        ('R002', 'WEEKDAY', 1, [(5, 2), (4, 2), (3, 2), (2, 2), (1, 2), (0, 2)], 8, 6, 'shp_002'),
        ('R002', 'WEEKEND', 0, [(0, 2), (1, 2), (2, 2), (3, 2), (4, 2), (5, 2)], 6, 8, 'shp_002'),
        ('R002', 'WEEKEND', 1, [(5, 2), (4, 2), (3, 2), (2, 2), (1, 2), (0, 2)], 6, 8, 'shp_002'),
        ('R003', 'WEEKDAY', 0, [(0, 0), (1, 1), (2, 2), (3, 3), (4, 4), (5, 5)], 6, 7, 'shp_003'),
        ('R003', 'WEEKDAY', 1, [(5, 5), (4, 4), (3, 3), (2, 2), (1, 1), (0, 0)], 6, 7, 'shp_003'),
        ('R004', 'WEEKDAY', 0, [(0, 0), (0, 5), (5, 5), (5, 0)], 5, 7, 'shp_004'),
        ('R004', 'WEEKDAY', 1, [(0, 0), (5, 0), (5, 5), (0, 5)], 5, 7, 'shp_004'),
        ('R005', 'WEEKDAY', 0, [(5, 0), (5, 1), (5, 2), (5, 3), (5, 4), (5, 5)], 4, 7, 'shp_005'),
        ('R005', 'WEEKDAY', 1, [(5, 5), (5, 4), (5, 3), (5, 2), (5, 1), (5, 0)], 4, 7, 'shp_005'),
    ]

    for route_id, service_id, direction, pattern, frequency, start_hour, shape_id in route_patterns:
        for hour in range(start_hour, start_hour + frequency * 2, 2):
            trip_id = f"T{trip_idx:04d}"
            trips.append({
                'route_id': route_id,
                'service_id': service_id,
                'trip_id': trip_id,
                'trip_headsign': f"{route_id}线-{'正向' if direction == 0 else '反向'}",
                'direction_id': direction,
                'shape_id': shape_id,
            })

            base_time = hour * 3600 + 30 * 60
            for seq, (row, col) in enumerate(pattern):
                stop_id = grid[(row, col)]
                arr_time = base_time + seq * 180
                dep_time = arr_time + 15

                h_a = arr_time // 3600
                m_a = (arr_time % 3600) // 60
                s_a = arr_time % 60

                h_d = dep_time // 3600
                m_d = (dep_time % 3600) // 60
                s_d = dep_time % 60

                stop_times.append({
                    'trip_id': trip_id,
                    'arrival_time': f"{h_a:02d}:{m_a:02d}:{s_a:02d}",
                    'departure_time': f"{h_d:02d}:{m_d:02d}:{s_d:02d}",
                    'stop_id': stop_id,
                    'stop_sequence': seq + 1,
                    'pickup_type': 0,
                    'drop_off_type': 0,
                })

            trip_idx += 1

    return trips, stop_times


def generate_shapes(grid):
    shapes = []
    shape_idx = 1

    shape_patterns = [
        ('shp_001', [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (0, 5)]),
        ('shp_002', [(0, 2), (1, 2), (2, 2), (3, 2), (4, 2), (5, 2)]),
        ('shp_003', [(0, 0), (1, 1), (2, 2), (3, 3), (4, 4), (5, 5)]),
        ('shp_004', [(0, 0), (0, 5), (5, 5), (5, 0)]),
        ('shp_005', [(5, 0), (5, 1), (5, 2), (5, 3), (5, 4), (5, 5)]),
    ]

    for shape_id, pattern in shape_patterns:
        dist = 0
        for seq, (row, col) in enumerate(pattern):
            lat = BASE_LAT + row * GRID_STEP
            lon = BASE_LON + col * GRID_STEP
            if seq > 0:
                prev_row, prev_col = pattern[seq - 1]
                prev_lat = BASE_LAT + prev_row * GRID_STEP
                prev_lon = BASE_LON + prev_col * GRID_STEP
                from geopy.distance import geodesic
                dist += geodesic((prev_lat, prev_lon), (lat, lon)).meters

            shapes.append({
                'shape_id': shape_id,
                'shape_pt_lat': lat,
                'shape_pt_lon': lon,
                'shape_pt_sequence': seq + 1,
                'shape_dist_traveled': round(dist, 2)
            })

    return shapes


def write_csv(filename, fieldnames, rows, dirpath):
    filepath = os.path.join(dirpath, filename)
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def create_gtfs_zip(output_dir):
    os.makedirs(output_dir, exist_ok=True)
    unzip_dir = os.path.join(output_dir, 'unzipped')
    os.makedirs(unzip_dir, exist_ok=True)

    stops, grid = generate_stops()
    routes = generate_routes()
    calendar = generate_calendar()
    calendar_dates = generate_calendar_dates()
    trips, stop_times = generate_trips_and_stop_times(grid)
    shapes = generate_shapes(grid)

    agency = [{
        'agency_id': 'AG001',
        'agency_name': '星辰公交公司',
        'agency_url': 'http://example.com',
        'agency_timezone': 'Asia/Shanghai',
        'agency_lang': 'zh',
        'agency_phone': '400-123-4567'
    }]

    write_csv('agency.txt', ['agency_id', 'agency_name', 'agency_url', 'agency_timezone', 'agency_lang', 'agency_phone'], agency, unzip_dir)
    write_csv('stops.txt', ['stop_id', 'stop_name', 'stop_lat', 'stop_lon', 'location_type'], stops, unzip_dir)
    write_csv('routes.txt', ['route_id', 'route_short_name', 'route_long_name', 'route_type', 'route_color'], routes, unzip_dir)
    write_csv('calendar.txt', ['service_id', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday', 'start_date', 'end_date'], calendar, unzip_dir)
    write_csv('calendar_dates.txt', ['service_id', 'date', 'exception_type'], calendar_dates, unzip_dir)
    write_csv('trips.txt', ['route_id', 'service_id', 'trip_id', 'trip_headsign', 'direction_id', 'shape_id'], trips, unzip_dir)
    write_csv('stop_times.txt', ['trip_id', 'arrival_time', 'departure_time', 'stop_id', 'stop_sequence', 'pickup_type', 'drop_off_type'], stop_times, unzip_dir)
    write_csv('shapes.txt', ['shape_id', 'shape_pt_lat', 'shape_pt_lon', 'shape_pt_sequence', 'shape_dist_traveled'], shapes, unzip_dir)

    zip_path = os.path.join(output_dir, 'sample_gtfs.zip')
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for filename in ['agency.txt', 'stops.txt', 'routes.txt', 'calendar.txt', 'calendar_dates.txt', 'trips.txt', 'stop_times.txt', 'shapes.txt']:
            zf.write(os.path.join(unzip_dir, filename), filename)

    print(f"Sample GTFS data generated at: {zip_path}")
    print(f"  Stops: {len(stops)}")
    print(f"  Routes: {len(routes)}")
    print(f"  Trips: {len(trips)}")
    print(f"  Stop times: {len(stop_times)}")
    print(f"  Shapes: {len(shapes)}")

    return zip_path


if __name__ == '__main__':
    output_dir = os.path.dirname(os.path.abspath(__file__))
    create_gtfs_zip(output_dir)
