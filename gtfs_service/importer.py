import csv
import io
import zipfile
from datetime import datetime, date
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from gtfs_service.models import (
    Agency, Stop, Route, Trip, StopTime, Calendar, CalendarDate, Shape
)


class GTFSImporter:
    GTFS_FILES = {
        'agency.txt': Agency,
        'stops.txt': Stop,
        'routes.txt': Route,
        'trips.txt': Trip,
        'stop_times.txt': StopTime,
        'calendar.txt': Calendar,
        'calendar_dates.txt': CalendarDate,
        'shapes.txt': Shape,
    }

    def __init__(self, db: Session):
        self.db = db
        self.stats = {}

    def import_gtfs_zip(self, zip_content: bytes) -> Dict[str, Any]:
        self.stats = {}
        self._clear_existing_data()

        with zipfile.ZipFile(io.BytesIO(zip_content), 'r') as zf:
            file_list = zf.namelist()

            for filename, model_class in self.GTFS_FILES.items():
                if filename in file_list:
                    self._import_file(zf, filename, model_class)

        self.db.commit()
        return self.stats

    def import_gtfs_directory(self, dir_path: str) -> Dict[str, Any]:
        import os
        self.stats = {}
        self._clear_existing_data()

        for filename, model_class in self.GTFS_FILES.items():
            filepath = os.path.join(dir_path, filename)
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8-sig') as f:
                    self._import_from_file(f, filename, model_class)

        self.db.commit()
        return self.stats

    def _clear_existing_data(self):
        for model_class in reversed(list(self.GTFS_FILES.values())):
            self.db.query(model_class).delete()
        self.db.commit()

    def _import_file(self, zf: zipfile.ZipFile, filename: str, model_class):
        with zf.open(filename, 'r') as f:
            text_io = io.TextIOWrapper(f, encoding='utf-8-sig')
            self._import_from_file(text_io, filename, model_class)

    def _import_from_file(self, text_io, filename: str, model_class):
        reader = csv.DictReader(text_io)
        rows = list(reader)
        count = 0
        batch_size = 1000
        batch = []

        for row in rows:
            try:
                obj = self._create_model_instance(model_class, row)
                batch.append(obj)
                count += 1

                if len(batch) >= batch_size:
                    self.db.bulk_save_objects(batch)
                    batch = []
            except Exception as e:
                print(f"Error importing {filename} row {count}: {e}")

        if batch:
            self.db.bulk_save_objects(batch)

        self.stats[filename] = count
        print(f"Imported {count} records from {filename}")

    def _create_model_instance(self, model_class, row: Dict[str, str]):
        cleaned = {}
        for key, value in row.items():
            if value is not None and value.strip() != '':
                cleaned[key.strip()] = value.strip()

        if model_class == Calendar:
            return self._create_calendar(cleaned)
        elif model_class == CalendarDate:
            return self._create_calendar_date(cleaned)
        elif model_class == StopTime:
            return self._create_stop_time(cleaned)
        elif model_class == Stop:
            return self._create_stop(cleaned)
        elif model_class == Shape:
            return self._create_shape(cleaned)
        else:
            return model_class(**self._convert_types(model_class, cleaned))

    def _convert_types(self, model_class, data: Dict[str, str]) -> Dict[str, Any]:
        result = {}
        for col in model_class.__table__.columns:
            if col.key in data:
                value = data[col.key]
                col_type = col.type.python_type

                try:
                    if col_type == int:
                        result[col.key] = int(value)
                    elif col_type == float:
                        result[col.key] = float(value)
                    elif col_type == bool:
                        result[col.key] = bool(int(value))
                    elif col_type == date:
                        result[col.key] = datetime.strptime(value, '%Y%m%d').date()
                    else:
                        result[col.key] = value
                except (ValueError, TypeError):
                    pass

        return result

    def _create_calendar(self, data: Dict[str, str]) -> Calendar:
        weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        obj_data = {'service_id': data.get('service_id', '')}

        for day in weekdays:
            obj_data[day] = bool(int(data.get(day, '0')))

        obj_data['start_date'] = datetime.strptime(data['start_date'], '%Y%m%d').date()
        obj_data['end_date'] = datetime.strptime(data['end_date'], '%Y%m%d').date()

        return Calendar(**obj_data)

    def _create_calendar_date(self, data: Dict[str, str]) -> CalendarDate:
        return CalendarDate(
            service_id=data.get('service_id', ''),
            date=datetime.strptime(data['date'], '%Y%m%d').date(),
            exception_type=int(data.get('exception_type', '1'))
        )

    def _create_stop_time(self, data: Dict[str, str]) -> StopTime:
        obj_data = {
            'trip_id': data.get('trip_id', ''),
            'arrival_time': data.get('arrival_time', ''),
            'departure_time': data.get('departure_time', ''),
            'stop_id': data.get('stop_id', ''),
            'stop_sequence': int(data.get('stop_sequence', '0')),
        }

        if 'stop_headsign' in data:
            obj_data['stop_headsign'] = data['stop_headsign']
        if 'pickup_type' in data:
            obj_data['pickup_type'] = int(data['pickup_type'])
        if 'drop_off_type' in data:
            obj_data['drop_off_type'] = int(data['drop_off_type'])
        if 'shape_dist_traveled' in data and data['shape_dist_traveled']:
            obj_data['shape_dist_traveled'] = float(data['shape_dist_traveled'])

        return StopTime(**obj_data)

    def _create_stop(self, data: Dict[str, str]) -> Stop:
        obj_data = {
            'stop_id': data.get('stop_id', ''),
            'stop_name': data.get('stop_name', ''),
            'stop_lat': float(data.get('stop_lat', '0')),
            'stop_lon': float(data.get('stop_lon', '0')),
        }

        optional_fields = ['stop_code', 'stop_desc', 'zone_id', 'stop_url', 'parent_station']
        for field in optional_fields:
            if field in data:
                obj_data[field] = data[field]

        if 'location_type' in data:
            obj_data['location_type'] = int(data['location_type'])
        if 'wheelchair_boarding' in data:
            obj_data['wheelchair_boarding'] = int(data['wheelchair_boarding'])

        return Stop(**obj_data)

    def _create_shape(self, data: Dict[str, str]) -> Shape:
        obj_data = {
            'shape_id': data.get('shape_id', ''),
            'shape_pt_lat': float(data.get('shape_pt_lat', '0')),
            'shape_pt_lon': float(data.get('shape_pt_lon', '0')),
            'shape_pt_sequence': int(data.get('shape_pt_sequence', '0')),
        }

        if 'shape_dist_traveled' in data and data['shape_dist_traveled']:
            obj_data['shape_dist_traveled'] = float(data['shape_dist_traveled'])

        return Shape(**obj_data)
