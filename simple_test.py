import urllib.request
import urllib.parse
import json
import datetime

BASE = "http://localhost:8010/api/v1"

def get(url):
    with urllib.request.urlopen(url) as r:
        return json.loads(r.read())

print("=== 1. 测试状态 ===")
status = get(f"{BASE}/status")
print(f"服务状态: {status['status']}")
print(f"站点: {status['stats']['stops']}, 线路: {status['stats']['routes']}, 班次: {status['stats']['trips']}")

print("\n=== 2. 测试站点列表 ===")
stops = get(f"{BASE}/stops")
for s in stops[:5]:
    print(f"  {s['stop_id']}: {s['stop_name']}")

print("\n=== 3. 测试线路列表 ===")
routes = get(f"{BASE}/routes")
for r in routes:
    print(f"  {r['route_id']}: {r['route_short_name']} - {r['route_long_name']}")

print("\n=== 4. 测试换乘查询 ===")
monday = (datetime.date.today() + datetime.timedelta(days=(7 - datetime.date.today().weekday() + 1) % 7))
dep_time = f"{monday.isoformat()} 08:30"
print(f"查询时间: {dep_time}")

params = urllib.parse.urlencode({
    'from_stop_id': 'S001',
    'to_stop_id': 'S036',
    'departure_time': dep_time
})
result = get(f"{BASE}/transfers?{params}")

print(f"\n从 {result['from_stop_name']} 到 {result['to_stop_name']}")
print(f"找到 {len(result['plans'])} 个换乘方案:")

for i, plan in enumerate(result['plans'][:5]):
    print(f"\n  --- 方案 {i+1} (评分: {plan['score']:.1f}) ---")
    print(f"  总耗时: {plan['total_duration_seconds']//60} 分钟")
    print(f"  换乘次数: {plan['transfers']}")
    print(f"  步行时间: {plan['total_walking_seconds']//60} 分钟")
    for j, seg in enumerate(plan['segments']):
        if seg['type'] == 'walk':
            print(f"  {j+1}. [步行] {seg['from_stop_name']} → {seg['to_stop_name']} ({seg['duration_seconds']//60}分钟)")
        else:
            print(f"  {j+1}. [乘车] {seg['route_name']} {seg['from_stop_name']}({seg['departure_time']}) → {seg['to_stop_name']}({seg['arrival_time']}) ({seg['duration_seconds']//60}分钟)")

print("\n=== 5. 测试数据校验 ===")
validation = get(f"{BASE}/validate")
print(f"校验错误数: {validation['total_errors']}")
if validation['errors']:
    for err in validation['errors'][:5]:
        print(f"  [{err['error_type']}] {err['message']}")
else:
    print("  数据校验通过，无错误！")

print("\n=== 测试完成 ===")
