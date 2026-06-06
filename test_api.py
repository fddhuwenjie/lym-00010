import urllib.request
import json
import datetime

BASE = "http://localhost:8010/api/v1"


def test_status():
    print("\n=== 1. 测试服务状态 ===")
    with urllib.request.urlopen(f"{BASE}/status") as r:
        data = json.loads(r.read())
        print(f"服务运行中: {data['status']}")
        print(f"数据统计: {json.dumps(data['stats'], indent=2, ensure_ascii=False)}")


def test_stops():
    print("\n=== 2. 测试站点查询 ===")
    with urllib.request.urlopen(f"{BASE}/stops") as r:
        data = json.loads(r.read())
        print(f"总站点数: {len(data)}")
        for s in data[:8]:
            print(f"  {s['stop_id']}: {s['stop_name']} ({s['stop_lat']:.4f}, {s['stop_lon']:.4f})")


def test_nearby():
    print("\n=== 3. 测试附近站点查询 ===")
    lat, lon = 31.2304, 121.4737
    with urllib.request.urlopen(f"{BASE}/stops/nearby?lat={lat}&lon={lon}&radius=1000") as r:
        data = json.loads(r.read())
        print(f"坐标 ({lat}, {lon}) 附近 1000m 内站点:")
        for s in data[:5]:
            print(f"  {s['stop_id']}: {s['stop_name']} - 距离 {s['distance']:.1f}m")


def test_routes():
    print("\n=== 4. 测试线路查询 ===")
    with urllib.request.urlopen(f"{BASE}/routes") as r:
        data = json.loads(r.read())
        print(f"总线路数: {len(data)}")
        for r in data:
            print(f"  {r['route_id']}: {r['route_short_name']} - {r['route_long_name']}")


def test_stops_routes():
    print("\n=== 5. 测试站点经过线路 ===")
    stop_id = "S003"
    with urllib.request.urlopen(f"{BASE}/stops/{stop_id}/routes") as r:
        data = json.loads(r.read())
        print(f"站点 {stop_id} 经过的线路:")
        for route in data:
            print(f"  {route['route_id']}: {route['route_short_name']}")


def test_schedule():
    print("\n=== 6. 测试时刻表查询 ===")
    route_id = "R001"
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
    print(f"查询线路 {route_id} 在 {tomorrow} 方向 0 的时刻表:")
    with urllib.request.urlopen(f"{BASE}/routes/{route_id}/schedule?target_date={tomorrow}&direction_id=0") as r:
        data = json.loads(r.read())
        print(f"  是否运营: {data['is_operating']}")
        print(f"  班次数量: {len(data['schedules'])}")
        if data['schedules']:
            first = data['schedules'][0]
            print(f"  首班 {first['trip_id']}:")
            for st in first['stop_times'][:3]:
                print(f"    {st['stop_sequence']}. {st['stop_name']} - 到 {st['arrival_time']} / 发 {st['departure_time']}")


def test_transfers():
    print("\n=== 7. 测试换乘查询 ===")
    from_stop = "S001"
    to_stop = "S036"
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1))
    dep_time = f"{tomorrow.isoformat()} 08:30"
    print(f"从 {from_stop} 到 {to_stop}, 出发时间 {dep_time}:")
    
    params = f"from_stop_id={from_stop}&to_stop_id={to_stop}&departure_time={urllib.parse.quote(dep_time)}"
    with urllib.request.urlopen(f"{BASE}/transfers?{params}") as r:
        data = json.loads(r.read())
        print(f"找到 {len(data['plans'])} 个换乘方案")
        
        for i, plan in enumerate(data['plans']):
            print(f"\n  方案 {i+1}:")
            print(f"    总耗时: {plan['total_duration_seconds']//60} 分钟")
            print(f"    换乘次数: {plan['transfers']}")
            print(f"    步行时间: {plan['total_walking_seconds']//60} 分钟")
            print(f"    分数(越低越好): {plan['score']:.1f}")
            print(f"    路段:")
            for seg in plan['segments']:
                if seg['type'] == 'walk':
                    print(f"      [步行] {seg['from_stop_name']} -> {seg['to_stop_name']} ({seg['duration_seconds']//60}分钟)")
                else:
                    print(f"      [乘车] {seg['route_name']} {seg['from_stop_name']}({seg['departure_time']}) -> {seg['to_stop_name']}({seg['arrival_time']}) ({seg['duration_seconds']//60}分钟)")


def test_validate():
    print("\n=== 8. 测试数据校验 ===")
    with urllib.request.urlopen(f"{BASE}/validate") as r:
        data = json.loads(r.read())
        print(f"校验错误总数: {data['total_errors']}")
        for err in data['errors'][:10]:
            print(f"  [{err['error_type']}] {err['message']}")


def test_delay():
    print("\n=== 9. 测试实时延误注入 ===")
    import http.client
    
    delay_data = json.dumps({"trip_id": "T0001", "delay_seconds": 180}).encode()
    headers = {"Content-Type": "application/json"}
    
    conn = http.client.HTTPConnection("localhost", 8010)
    conn.request("POST", f"{BASE}/delay", delay_data, headers)
    response = conn.getresponse()
    result = json.loads(response.read())
    print(f"注入延误: {result['message']}")
    
    with urllib.request.urlopen(f"{BASE}/status") as r:
        data = json.loads(r.read())
        print(f"当前活跃延误数: {data['stats']['active_delays']}")


if __name__ == "__main__":
    try:
        test_status()
        test_stops()
        test_nearby()
        test_routes()
        test_stops_routes()
        test_schedule()
        test_transfers()
        test_validate()
        test_delay()
        print("\n=== 所有测试完成 ===")
    except Exception as e:
        print(f"测试出错: {e}")
        import traceback
        traceback.print_exc()
