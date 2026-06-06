#!/usr/bin/env python
import json
import sys
import io
import urllib.request
import urllib.parse
import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = "http://localhost:8010/api/v1"
monday = (datetime.date.today() + datetime.timedelta(days=(7 - datetime.date.today().weekday() + 1) % 7))

print("=" * 70)
print("  GTFS 换乘查询 - Bug 修复验证")
print("=" * 70)
print()
print("测试用例: S001 (Central East Station) -> S036 (Suburb New Station)")
print("出发时间: " + str(monday) + " 08:30")
print()

params = urllib.parse.urlencode({
    'from_stop_id': 'S001',
    'to_stop_id': 'S036',
    'departure_time': str(monday) + ' 08:30'
})
with urllib.request.urlopen(BASE + "/transfers?" + params, timeout=15) as r:
    data = json.loads(r.read().decode('utf-8'))

print("-" * 70)
print("  [问题1验证] 换乘次数计算")
print("-" * 70)
print()

has_error = False
prev_duration = None
seen_durations = {}

for i, plan in enumerate(data['plans'][:5], 1):
    ride_segments = [s for s in plan['segments'] if s['type'] == 'ride']
    expected_transfers = max(0, len(ride_segments) - 1) if ride_segments else 0
    actual_transfers = plan['transfers']

    status = "✓" if actual_transfers == expected_transfers else "✗"
    if actual_transfers != expected_transfers:
        has_error = True
    print(f"  方案 {i}: 乘车段数={len(ride_segments)}, 实际换乘次数={actual_transfers}, 预期={expected_transfers} {status}")

    if prev_duration is not None and plan['total_duration_seconds'] == prev_duration:
        route_key = '->'.join([s.get('route_name', 'WALK') for s in plan['segments']])
        if route_key not in seen_durations:
            seen_durations[route_key] = []
        seen_durations[route_key].append(plan['total_duration_seconds'])

    prev_duration = plan['total_duration_seconds']

print()
print("-" * 70)
print("  [问题2验证] 同耗时不同结构 / 去重效果")
print("-" * 70)
print()

all_durations = [p['total_duration_seconds'] for p in data['plans']]
unique_durations = set(all_durations)
print(f"  总方案数: {len(data['plans'])}")
print(f"  不同总耗时数量: {len(unique_durations)}")
print()

if len(all_durations) != len(unique_durations):
    from collections import Counter
    counts = Counter(all_durations)
    for dur, cnt in counts.items():
        if cnt > 1:
            print(f"  ⚠  耗时 {dur//60} 分钟 出现 {cnt} 次")

print()
print("-" * 70)
print("  [问题3验证] 绕远多余方案")
print("-" * 70)
print()

has_roundabout = False
for i, plan in enumerate(data['plans'][:5], 1):
    stops_in_path = set()
    has_duplicate_stops = False
    for seg in plan['segments']:
        if seg['from_stop_id'] in stops_in_path or seg['to_stop_id'] in stops_in_path:
            has_duplicate_stops = True
            has_roundabout = True
        stops_in_path.add(seg['from_stop_id'])
        stops_in_path.add(seg['to_stop_id'])

    status = "⚠ 可能绕远" if has_duplicate_stops else "✓ 无重复站点"
    print(f"  方案 {i}: {status}")

print()
print("-" * 70)
print("  详细方案信息")
print("-" * 70)
print()

for i, plan in enumerate(data['plans'][:5], 1):
    print(f"  方案 {i} (评分: {plan['score']:.1f})")
    print(f"    总耗时: {plan['total_duration_seconds']//60} 分钟")
    print(f"    换乘次数: {plan['transfers']}")
    print(f"    步行时间: {plan['total_walking_seconds']//60} 分钟")
    print(f"    路径:")
    for j, seg in enumerate(plan['segments'], 1):
        if seg['type'] == 'walk':
            print(f"      {j}. [步行] {seg['from_stop_name']} -> {seg['to_stop_name']} ({seg['duration_seconds']//60}分钟)")
        else:
            print(f"      {j}. [乘车] {seg['route_name']} {seg['from_stop_name']}({seg['departure_time']}) -> {seg['to_stop_name']}({seg['arrival_time']}) ({seg['duration_seconds']//60}分钟)")
    print()

print("=" * 70)
if not has_error and not has_roundabout:
    print("  ✓ 所有问题已修复！")
else:
    print("  ⚠  仍有问题需要检查")
print("=" * 70)
