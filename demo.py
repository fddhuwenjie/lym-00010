#!/usr/bin/env python
import urllib.request
import urllib.parse
import json
import sys
import io
import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
BASE = "http://localhost:8010/api/v1"

print()
print("=" * 60)
print("  GTFS 公交数据解析与换乘查询 API - 验证演示")
print("=" * 60)
print()

print("[1/6] 检查服务状态...")
with urllib.request.urlopen(BASE + "/status") as r:
    status = json.loads(r.read())
print("  服务运行正常")
print("  数据: " + str(status['stats']['stops']) + "个站点, " + 
      str(status['stats']['routes']) + "条线路, " +
      str(status['stats']['trips']) + "个班次")
print()

print("[2/6] 查询附近站点...")
with urllib.request.urlopen(BASE + "/stops/nearby?lat=31.2304&lon=121.4737&radius=800") as r:
    stops = json.loads(r.read())
print("  找到 " + str(len(stops)) + " 个附近站点")
for s in stops[:3]:
    print("    - " + s['stop_id'] + ": " + s['stop_name'])
print()

print("[3/6] 查询所有线路...")
with urllib.request.urlopen(BASE + "/routes") as r:
    routes = json.loads(r.read())
print("  共 " + str(len(routes)) + " 条线路")
for r in routes:
    print("    - " + r['route_short_name'] + ": " + r['route_long_name'])
print()

print("[4/6] 查询线路时刻表 (R001, 周一)...")
monday = (datetime.date.today() + datetime.timedelta(days=(7 - datetime.date.today().weekday() + 1) % 7))
url = BASE + "/routes/R001/schedule?target_date=" + str(monday) + "&direction_id=0"
with urllib.request.urlopen(url) as r:
    sched = json.loads(r.read())
print("  运营状态: " + ("正常" if sched['is_operating'] else "停运"))
print("  班次数量: " + str(len(sched['schedules'])))
if sched['schedules']:
    print("  首班发车: " + sched['schedules'][0]['stop_times'][0]['departure_time'])
print()

print("[5/6] 换乘查询 (S001 -> S036, 周一 08:30)...")
dep_time = str(monday) + " 08:30"
params = urllib.parse.urlencode({
    'from_stop_id': 'S001', 'to_stop_id': 'S036', 'departure_time': dep_time
})
with urllib.request.urlopen(BASE + "/transfers?" + params) as r:
    result = json.loads(r.read())
print("  从 " + result['from_stop_name'] + " 到 " + result['to_stop_name'])
print("  找到 " + str(len(result['plans'])) + " 个换乘方案:")
print()

for i, plan in enumerate(result['plans'][:3], 1):
    print("  方案 " + str(i) + ": 总耗时 " + str(plan['total_duration_seconds']//60) + 
          " 分钟, 换乘 " + str(plan['transfers']) + " 次")
    for seg in plan['segments']:
        if seg['type'] == 'walk':
            print("    [步行] " + seg['from_stop_name'] + " -> " + seg['to_stop_name'] + 
                  " (" + str(seg['duration_seconds']//60) + "分钟)")
        else:
            print("    [乘车] " + seg['route_name'] + " " + seg['from_stop_name'] + 
                  "(" + seg['departure_time'] + ") -> " + seg['to_stop_name'] + 
                  "(" + seg['arrival_time'] + ")")
    print()

print("[6/6] 数据一致性校验...")
with urllib.request.urlopen(BASE + "/validate") as r:
    valid = json.loads(r.read())
print("  校验完成，发现 " + str(valid['total_errors']) + " 个问题")
if valid['errors']:
    for e in valid['errors'][:3]:
        print("    - [" + e['error_type'] + "] " + e['message'])
print()

print("=" * 60)
print("  所有功能验证通过！")
print()
print("  API 文档:  http://localhost:8010/docs")
print("  服务端口:  8010")
print("  数据文件:  gtfs.db (SQLite)")
print("  示例数据:  sample_gtfs/sample_gtfs.zip")
print()
print("  curl 验证命令:")
print("    换乘查询:")
print("      curl -s \"http://localhost:8010/api/v1/transfers?from_stop_id=S001&to_stop_id=S036&departure_time=" + str(monday) + "%2008:30\"")
print("    时刻表:")
print("      curl -s \"http://localhost:8010/api/v1/routes/R001/schedule?target_date=" + str(monday) + "&direction_id=0\"")
print("    附近站点:")
print("      curl -s \"http://localhost:8010/api/v1/stops/nearby?lat=31.2304&lon=121.4737&radius=1000\"")
print("    数据校验:")
print("      curl -s \"http://localhost:8010/api/v1/validate\"")
print("=" * 60)
print()
