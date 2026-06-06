import os
import sys
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gtfs_service.database import Base, engine, SessionLocal
from gtfs_service.api import router as api_router
from gtfs_service.models import Stop, Route, Trip, StopTime
from gtfs_service.importer import GTFSImporter

app = FastAPI(
    title="GTFS 公交数据解析与换乘查询 API",
    description="标准 GTFS 数据导入、站点线路查询、时刻表查询、换乘路径规划、实时延误、数据校验",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1", tags=["GTFS API"])


def init_database():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created.")


def init_sample_data():
    db = SessionLocal()
    try:
        stop_count = db.query(Stop).count()
        route_count = db.query(Route).count()

        if stop_count > 0 and route_count > 0:
            print(f"Database already has data: {stop_count} stops, {route_count} routes. Skipping initialization.")
            return

        print("Generating sample GTFS data...")
        sample_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_gtfs")
        sys.path.insert(0, sample_dir)

        from generate_sample import create_gtfs_zip
        zip_path = create_gtfs_zip(sample_dir)

        print("Importing sample GTFS data...")
        with open(zip_path, 'rb') as f:
            zip_content = f.read()

        importer = GTFSImporter(db)
        stats = importer.import_gtfs_zip(zip_content)

        print("Sample data imported successfully:")
        for key, value in stats.items():
            print(f"  {key}: {value}")

    except Exception as e:
        print(f"Error initializing sample data: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


@app.get("/")
def root():
    return {
        "name": "GTFS 公交数据解析与换乘查询 API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "import": "POST /api/v1/import",
            "nearby_stops": "GET /api/v1/stops/nearby?lat=&lon=&radius=",
            "all_stops": "GET /api/v1/stops",
            "stop_detail": "GET /api/v1/stops/{stop_id}",
            "routes_at_stop": "GET /api/v1/stops/{stop_id}/routes",
            "all_routes": "GET /api/v1/routes",
            "route_detail": "GET /api/v1/routes/{route_id}",
            "route_schedule": "GET /api/v1/routes/{route_id}/schedule?date=&direction_id=",
            "transfers": "GET /api/v1/transfers?from_stop_id=&to_stop_id=&departure_time=",
            "inject_delay": "POST /api/v1/delay",
            "clear_delays": "DELETE /api/v1/delay",
            "validate": "GET /api/v1/validate",
            "status": "GET /api/v1/status",
        }
    }


@app.on_event("startup")
async def startup_event():
    print("\n" + "=" * 60)
    print("  GTFS 公交数据解析与换乘查询 API 服务启动中...")
    print("=" * 60)

    init_database()
    init_sample_data()

    print("\n" + "=" * 60)
    print("  服务启动完成! 监听端口: 8010")
    print("  API 文档: http://localhost:8010/docs")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8010, reload=False)
