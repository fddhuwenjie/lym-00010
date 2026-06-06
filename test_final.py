#!/usr/bin/env python
import json
import urllib.request
import urllib.parse
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = "http://localhost:8010/api/v1"

params = urllib.parse.urlencode({
    'from_stop_id': 'S001',
    'to_stop_id': 'S036',
    'departure_time': '2026-06-08 08:30'
})
url = BASE + "/transfers?" + params
print("URL:", url)
print()

try:
    with urllib.request.urlopen(url, timeout=30) as r:
        data = json.loads(r.read().decode('utf-8'))
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)

print(f"测试用例: S001 -> S036, 2026-06-08 08:30")
print(f"返回方案数: {len(data['plans'])}")
print()
print("=" * 80)

for i, plan in enumerate(data['plans'], 1):
    ride_segments = [s for s in plan['segments'] if s['type'] == 'ride']
    expected_transfers = max(0, len(ride_segments) - 1) if ride_segments else 0
    
    print(f"\n方案 {i}:")
    print(f"  总耗时: {plan['total_duration_seconds']//60} 分钟 ({plan['total_duration_seconds']}s)")
    print(f"  换乘次数: {plan['transfers']} (实际乘车段: {len(ride_segments)}, 预期换乘: {expected_transfers})")
    print(f"  评分: {plan['score']:.1f}")
    print(f"  路径:")
    for j, seg in enumerate(plan['segments'], 1):
        if seg['type'] == 'walk':
            print(f"    {j}. [步行] {seg['from_stop_name']} -> {seg['to_stop_name']} ({seg['duration_seconds']//60}分钟)")
        else:
            print(f"    {j}. [乘车] {seg['route_name']} {seg['from_stop_name']}({seg['departure_time']}) -> {seg['to_stop_name']}({seg['arrival_time']}) ({seg['duration_seconds']//60}分钟)")

print()
print("=" * 80)

durations = [p['total_duration_seconds'] for p in data['plans']]
transfers_list = [p['transfers'] for p in data['plans']]

print("\n验证结果:")
print(f"  不同耗时: {set(durations)}")
print(f"  换乘次数: {transfers_list}")

# 检查问题
has_issue = False
prev_dur = None
for i, plan in enumerate(data['plans']):
    ride = [s for s in plan['segments'] if s['type'] == 'ride']
    expected = max(0, len(ride) - 1) if ride else 0
    if plan['transfers'] != expected:
        print(f"  ✗ 方案 {i+1}: 换乘次数错误: 实际{plan['transfers']}, 预期{expected}")
        has_issue = True

if max(transfers_list, default=0) > 3:
    print(f"  ✗ 存在超过3次换乘的方案")
    has_issue = True

# 检查绕远
for i, plan in enumerate(data['plans']):
    stops = []
    for seg in plan['segments']:
        stops.append(seg['from_stop_id'])
        stops.append(seg['to_stop_id'])
    if len(stops) != len(set(stops)):
        print(f"  ⚠  方案 {i+1}: 存在重复站点，可能绕远")
        has_issue = True

if not has_issue:
    print("  ✓ 所有问题已修复！")
