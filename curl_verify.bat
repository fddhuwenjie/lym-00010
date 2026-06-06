@echo off
echo ========================================
echo  GTFS API 验证脚本
echo ========================================

echo.
echo [1] 测试服务状态
curl.exe -s http://localhost:8010/api/v1/status
echo.

echo.
echo [2] 测试附近站点查询
curl.exe -s "http://localhost:8010/api/v1/stops/nearby?lat=31.2304&lon=121.4737&radius=1000"
echo.

echo.
echo [3] 测试所有线路
curl.exe -s http://localhost:8010/api/v1/routes
echo.

echo.
echo [4] 测试站点经过线路
curl.exe -s http://localhost:8010/api/v1/stops/S003/routes
echo.

echo.
echo [5] 测试线路时刻表
curl.exe -s "http://localhost:8010/api/v1/routes/R001/schedule?target_date=2026-06-08&direction_id=0"
echo.

echo.
echo [6] 测试换乘查询 (S001 - S036)
curl.exe -s "http://localhost:8010/api/v1/transfers?from_stop_id=S001&to_stop_id=S036&departure_time=2026-06-08%%2008:30"
echo.

echo.
echo [7] 测试注入实时延误
curl.exe -s -X POST -H "Content-Type: application/json" -d "{\"trip_id\":\"T0001\",\"delay_seconds\":180}" http://localhost:8010/api/v1/delay
echo.

echo.
echo [8] 测试数据校验
curl.exe -s http://localhost:8010/api/v1/validate
echo.

echo.
echo ========================================
echo  验证完成
echo ========================================
