import urllib.request
import urllib.parse
import json
import datetime

BASE = "http://localhost:8010/api/v1"

print("=== 调试换乘查询 ===")

print("\n1. 先测试周一（工作日）的时刻表...")
monday = (datetime.date.today() + datetime.timedelta(days=(7 - datetime.date.today().weekday() + 1) % 7))
print(f"周一日期: {monday}")

with urllib.request.urlopen(f"{BASE}/routes/R001/schedule?target_date={monday}&direction_id=0") as r:
    data = json.loads(r.read())
    print(f"R001 周一运营: {data['is_operating']}, 班次: {len(data['schedules'])}")
    if data['schedules']:
        print(f"首班发车时间: {data['schedules'][0]['stop_times'][0]['departure_time']}")
        print(f"末班发车时间: {data['schedules'][-1]['stop_times'][0]['departure_time']}")

print("\n2. 测试 R002 周一时刻表...")
with urllib.request.urlopen(f"{BASE}/routes/R002/schedule?target_date={monday}&direction_id=0") as r:
    data = json.loads(r.read())
    print(f"R002 周一运营: {data['is_operating']}, 班次: {len(data['schedules'])}")
    if data['schedules']:
        print(f"首班发车时间: {data['schedules'][0]['stop_times'][0]['departure_time']}")

print("\n3. 测试 S003 站点经过的线路...")
with urllib.request.urlopen(f"{BASE}/stops/S003/routes") as r:
    data = json.loads(r.read())
    print(f"S003 经过线路: {[r['route_short_name'] for r in data]}")

print("\n4. 测试换乘查询（周一 08:30）...")
from_stop = "S001"
to_stop = "S036"
dep_time = f"{monday.isoformat()} 08:30"
print(f"从 {from_stop} 到 {to_stop}, 出发时间 {dep_time}")

params = f"from_stop_id={from_stop}&to_stop_id={to_stop}&departure_time={urllib.parse.quote(dep_time)}"
with urllib.request.urlopen(f"{BASE}/transfers?{params}") as r:
    data = json.loads(r.read())
    print(f"找到 {len(data['plans'])} 个换乘方案")
    
    for i, plan in enumerate(data['plans'][:3]):
        print(f"\n  方案 {i+1}: 总耗时 {plan['total_duration_seconds']//60}分钟, 换乘 {plan['transfers']}次")
        for seg in plan['segments']:
            if seg['type'] == 'walk':
                print(f"    [步行] {seg['from_stop_name']} -> {seg['to_stop_name']} ({seg['duration_seconds']//60}分钟)")
            else:
                print(f"    [乘车] {seg['route_name']} {seg['from_stop_name']}({seg['departure_time']}) -> {seg['to_stop_name']}({seg['arrival_time']})")

print("\n5. 测试短途换乘（S001 -> S019）...")
to_stop2 = "S019"
params2 = f"from_stop_id={from_stop}&to_stop_id={to_stop2}&departure_time={urllib.parse.quote(dep_time)}"
with urllib.request.urlopen(f"{BASE}/transfers?{params2}") as r:
    data = json.loads(r.read())
    print(f"从 S001 到 S019: 找到 {len(data['plans'])} 个方案")
    for i, plan in enumerate(data['plans'][:3]):
        print(f"  方案 {i+1}: {plan['total_duration_seconds']//60}分钟, {plan['transfers']}次换乘")
        for seg in plan['segments']:
            if seg['type'] == 'ride':
                print(f"    {seg['route_name']}: {seg['from_stop_name']}({seg['departure_time']}) -> {seg['to_stop_name']}({seg['arrival_time']})")
