import urllib.request
import urllib.parse
import json
import datetime

BASE = "http://localhost:8010/api/v1"

print("=== 测试换乘查询 ===")
from_stop = "S001"
to_stop = "S036"
tomorrow = (datetime.date.today() + datetime.timedelta(days=1))
dep_time = f"{tomorrow.isoformat()} 08:30"
print(f"从 {from_stop} 到 {to_stop}, 出发时间 {dep_time}")

params = f"from_stop_id={from_stop}&to_stop_id={to_stop}&departure_time={urllib.parse.quote(dep_time)}"
url = f"{BASE}/transfers?{params}"
print(f"请求 URL: {url}")

try:
    with urllib.request.urlopen(url) as r:
        data = json.loads(r.read())
        print(f"\n找到 {len(data['plans'])} 个换乘方案")
        
        for i, plan in enumerate(data['plans']):
            print(f"\n  方案 {i+1}:")
            print(f"    总耗时: {plan['total_duration_seconds']//60} 分钟")
            print(f"    换乘次数: {plan['transfers']}")
            print(f"    步行时间: {plan['total_walking_seconds']//60} 分钟")
            print(f"    路段:")
            for seg in plan['segments']:
                if seg['type'] == 'walk':
                    print(f"      [步行] {seg['from_stop_name']} -> {seg['to_stop_name']} ({seg['duration_seconds']//60}分钟)")
                else:
                    print(f"      [乘车] {seg['route_name']} {seg['from_stop_name']}({seg['departure_time']}) -> {seg['to_stop_name']}({seg['arrival_time']}) ({seg['duration_seconds']//60}分钟)")
except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
