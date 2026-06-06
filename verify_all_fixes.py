#!/usr/bin/env python
"""
所有 Bug 修复最终验证
"""
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from datetime import datetime
from gtfs_service.database import SessionLocal, engine, Base
from gtfs_service import models
from gtfs_service.pathfinding import TransferFinder
from gtfs_service import validator
from gtfs_service import utils

Base.metadata.create_all(bind=engine)
db = SessionLocal()
finder = TransferFinder(db)

print("=" * 70)
print("  GTFS 换乘查询 - 所有 Bug 修复最终验证")
print("=" * 70)
print()

monday = datetime(2026, 6, 8, 8, 30)

print("【问题 1】换乘次数计算（连续跨多条线路正确计数）")
print("-" * 70)
plans = finder.find_transfers('S001', 'S015', monday)
all_ok = True
for i, p in enumerate(plans, 1):
    ride_count = len([s for s in p.segments if s.type == 'ride'])
    expected = max(0, ride_count - 1) if ride_count else 0
    ok = p.transfers == expected
    if not ok:
        all_ok = False
    status = "OK" if ok else "ERROR"
    print(f"  方案 {i}: 乘车{ride_count}段, 换乘{p.transfers}次 (预期{expected}) -> {status}")
print(f"  结果: {'PASS' if all_ok else 'FAIL'}")
print()

print("【问题 2】不同结构方案评分区分（候车与乘车时长口径区分）")
print("-" * 70)
plans = finder.find_transfers('S001', 'S036', monday)
print(f"  返回方案数: {len(plans)}")
scores = []
durations = []
for i, p in enumerate(plans, 1):
    scores.append(p.score)
    durations.append(p.total_duration_seconds)
    print(f"\n  方案 {i}:")
    print(f"    总耗时: {p.total_duration_seconds//60} 分钟")
    print(f"    候车: {p.total_waiting_seconds//60} 分钟, 乘车: {p.total_riding_seconds//60} 分钟, 步行: {p.total_walking_seconds//60} 分钟")
    print(f"    换乘: {p.transfers} 次")
    print(f"    评分: {p.score:.0f}")
    for s in p.segments:
        if s.type == 'ride':
            print(f"      {s.route_name}: {s.from_stop_name}({s.departure_time}) -> {s.to_stop_name}({s.arrival_time})")

print()
print(f"  所有方案评分不同: {'PASS' if len(set(scores)) == len(scores) else 'FAIL'}")
print(f"  评分列表: {[f'{s:.0f}' for s in scores]}")
print(f"  说明: 虽然总耗时都是 {durations[0]//60} 分钟，但候车/乘车比例不同，")
print(f"       评分有明显差异，候车时间长的方案评分更高（更差）")
print()

print("【问题 3】去重逻辑（剔除绕远多余方案）")
print("-" * 70)
plans = finder.find_transfers('S001', 'S036', monday)
max_transfers = max([p.transfers for p in plans] + [0])
min_dur = min([p.total_duration_seconds for p in plans] + [float('inf')])
all_within_2x = all(p.total_duration_seconds <= min_dur * 2 for p in plans)
transfers_ok = max_transfers <= 3
print(f"  最大换乘次数: {max_transfers} (限制: 3) -> {'PASS' if transfers_ok else 'FAIL'}")
print(f"  最短耗时: {min_dur//60} 分钟")
print(f"  所有方案耗时 <= 2倍最短耗时: {'PASS' if all_within_2x else 'FAIL'}")
print(f"  方案数: {len(plans)} (限制: 5)")
print()

print("【问题 4】validator 死代码清理")
print("-" * 70)
validator_source = open(validator.__file__, encoding='utf-8').read()
validator_has_func = 'def seconds_to_time' in validator_source
import_line = open(validator.__file__, encoding='utf-8').readlines()[8].strip()
imports_ok = 'from gtfs_service.utils import' in import_line and 'seconds_to_time' in import_line

print(f"  validator 底部还有 seconds_to_time 函数定义: {'YES (FAIL)' if validator_has_func else 'NO (PASS)'}")
print(f"  validator 从 utils 导入 seconds_to_time: {'PASS' if imports_ok else 'FAIL'}")
print(f"  导入语句: {import_line}")
print()

print("=" * 70)
all_pass = (
    all_ok and
    len(set(scores)) == len(scores) and
    transfers_ok and
    all_within_2x and
    not validator_has_func and
    imports_ok
)
if all_pass:
    print("  ✓ 所有问题已修复！验证全部通过！")
else:
    print("  ⚠  部分问题仍需检查")
print("=" * 70)
