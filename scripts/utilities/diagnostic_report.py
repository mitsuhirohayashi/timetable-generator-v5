#!/usr/bin/env python3
"""時間割生成の診断レポートを作成するツール"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.domain.services.unified_constraint_validator import UnifiedConstraintValidator
from src.infrastructure.parsers.enhanced_followup_parser import EnhancedFollowUpParser
from collections import defaultdict
import json

def analyze_constraint_conflicts():
    """制約の競合関係を分析"""
    # データ読み込み
    repo = CSVScheduleRepository()
    
    # 学校データとスケジュール読み込み
    school = repo.load_school_data()
    schedule = repo.load('data/output/output.csv', school)
    
    # Follow-up情報読み込み
    followup_parser = EnhancedFollowUpParser()
    followup_constraints = followup_parser.parse('data/input/Follow-up.csv')
    
    # 制約検証
    validator = UnifiedConstraintValidator(school, followup_constraints)
    violations = validator.validate(schedule)
    
    # 違反の分析
    violation_summary = defaultdict(list)
    conflict_patterns = defaultdict(int)
    
    for v in violations:
        violation_summary[v.constraint_name].append({
            'details': v.details,
            'location': f"{v.day} {v.period}限 {v.class_name}" if v.day and v.period and v.class_name else "不明"
        })
        
        # 競合パターンの特定
        if "教師重複" in v.constraint_name and "5組" in v.details:
            conflict_patterns["5組関連の教師重複"] += 1
        elif "教師重複" in v.constraint_name:
            conflict_patterns["通常の教師重複"] += 1
        elif "5組同期" in v.constraint_name:
            conflict_patterns["5組同期違反"] += 1
    
    # レポート生成
    report = {
        "総違反数": len(violations),
        "違反タイプ別": {name: len(items) for name, items in violation_summary.items()},
        "競合パターン": dict(conflict_patterns),
        "詳細": {}
    }
    
    # 最も問題の多い制約の詳細を追加
    for constraint_name, items in sorted(violation_summary.items(), key=lambda x: len(x[1]), reverse=True)[:3]:
        report["詳細"][constraint_name] = items[:5]  # 上位5件のみ
    
    return report

def analyze_teacher_workload():
    """教師の負担分析"""
    repo = CSVScheduleRepository()
    schedule = repo.load('data/output/output.csv', school)
    
    teacher_hours = defaultdict(int)
    teacher_conflicts = defaultdict(list)
    
    for day_idx, day_name in enumerate(['月', '火', '水', '木', '金']):
        for period in range(6):
            classes_by_teacher = defaultdict(list)
            
            for class_name, day_schedule in schedule.assignments.items():
                if day_idx < len(day_schedule) and period < len(day_schedule[day_idx]):
                    assignment = day_schedule[day_idx][period]
                    if assignment and assignment.teacher_name:
                        teacher_hours[assignment.teacher_name] += 1
                        classes_by_teacher[assignment.teacher_name].append(class_name)
            
            # 重複チェック
            for teacher, classes in classes_by_teacher.items():
                if len(classes) > 1:
                    # 5組の合同授業は除外
                    grade5_classes = [c for c in classes if c.endswith('5')]
                    if not (len(grade5_classes) == len(classes) and len(set(classes)) == 3):
                        teacher_conflicts[teacher].append({
                            'day': day_name,
                            'period': period + 1,
                            'classes': classes
                        })
    
    # 負担分析
    avg_hours = sum(teacher_hours.values()) / len(teacher_hours) if teacher_hours else 0
    workload_analysis = {
        "平均授業時数": round(avg_hours, 1),
        "過負荷教師": {t: h for t, h in teacher_hours.items() if h > avg_hours * 1.2},
        "低負荷教師": {t: h for t, h in teacher_hours.items() if h < avg_hours * 0.8},
        "重複問題教師": {t: len(c) for t, c in teacher_conflicts.items() if c}
    }
    
    return workload_analysis

def generate_improvement_suggestions():
    """改善提案の生成"""
    constraint_report = analyze_constraint_conflicts()
    workload_report = analyze_teacher_workload()
    
    suggestions = []
    
    # 5組関連の提案
    if constraint_report["競合パターン"].get("5組関連の教師重複", 0) > 0:
        suggestions.append({
            "問題": "5組の合同授業での教師重複",
            "原因": "5組を個別に配置してから同期を試みているため",
            "対策": "5組を最初に一括配置し、金子み先生を5組専任として優先割り当て"
        })
    
    # 教師重複の提案
    if constraint_report["違反タイプ別"].get("教師重複制約", 0) > 10:
        suggestions.append({
            "問題": "多数の教師重複違反",
            "原因": "配置時に教師の可用性チェックが不十分",
            "対策": "配置前に教師スケジュールをリアルタイムで追跡し、事前チェックを強化"
        })
    
    # 負荷バランスの提案
    if len(workload_report["過負荷教師"]) > 3:
        suggestions.append({
            "問題": "特定教師への負荷集中",
            "原因": "教師の専門性と可用性のバランスが取れていない",
            "対策": "負荷分散を考慮した配置アルゴリズムの導入"
        })
    
    return suggestions

def main():
    print("=== 時間割生成診断レポート ===\n")
    
    # 制約違反分析
    print("1. 制約違反分析")
    constraint_report = analyze_constraint_conflicts()
    print(f"  総違反数: {constraint_report['総違反数']}")
    print("  違反タイプ別:")
    for name, count in sorted(constraint_report['違反タイプ別'].items(), key=lambda x: x[1], reverse=True):
        print(f"    - {name}: {count}件")
    
    # 教師負担分析
    print("\n2. 教師負担分析")
    workload_report = analyze_teacher_workload()
    print(f"  平均授業時数: {workload_report['平均授業時数']}時間")
    print(f"  過負荷教師数: {len(workload_report['過負荷教師'])}人")
    print(f"  重複問題のある教師数: {len(workload_report['重複問題教師'])}人")
    
    # 改善提案
    print("\n3. 改善提案")
    suggestions = generate_improvement_suggestions()
    for i, suggestion in enumerate(suggestions, 1):
        print(f"\n  提案{i}: {suggestion['問題']}")
        print(f"    原因: {suggestion['原因']}")
        print(f"    対策: {suggestion['対策']}")
    
    # 詳細レポートをファイルに保存
    detailed_report = {
        "制約違反分析": constraint_report,
        "教師負担分析": workload_report,
        "改善提案": suggestions
    }
    
    with open('diagnostic_report.json', 'w', encoding='utf-8') as f:
        json.dump(detailed_report, f, ensure_ascii=False, indent=2)
    
    print("\n詳細レポートを diagnostic_report.json に保存しました。")

if __name__ == "__main__":
    main()