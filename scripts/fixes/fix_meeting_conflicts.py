#!/usr/bin/env python3
"""会議時間の制約違反を修正するスクリプト"""

import pandas as pd
from pathlib import Path
from collections import defaultdict

def fix_meeting_conflicts():
    """会議時間の制約違反を修正"""
    
    # ファイル読み込み
    input_path = Path(__file__).parent / "data" / "output" / "output.csv"
    output_path = Path(__file__).parent / "data" / "output" / "output_meetings_fixed.csv"
    
    df = pd.read_csv(input_path, header=None)
    days = df.iloc[0, 1:].tolist()
    periods = df.iloc[1, 1:].tolist()
    
    print("=== 会議時間の制約違反修正 ===\n")
    
    def get_cell(day, period):
        for i, (d, p) in enumerate(zip(days, periods)):
            if d == day and str(p) == str(period):
                return i + 1
        return None
    
    def get_class_row(class_name):
        for i in range(2, len(df)):
            if df.iloc[i, 0] == class_name:
                return i
        return None
    
    def is_fixed_subject(subject):
        """固定科目かチェック"""
        return subject in ["欠", "YT", "道", "道徳", "学", "学活", "学総", "総", "総合", "行", "テスト"]
    
    # 会議設定
    meetings = {
        "特会": {
            "time": ("月", "4"),
            "teachers": ["金子み", "智田", "井上", "財津"],
            "violations": [
                ("1年3組", "家", "金子み"),
                ("2年2組", "理", "智田"),
                ("2年3組", "数", "井上"),
                ("3年2組", "保", "財津")
            ]
        },
        "企画": {
            "time": ("木", "3"),
            "teachers": ["井上", "林", "蒲地", "小野塚", "寺田"],
            "violations": [
                ("1年1組", "国", "寺田")
            ]
        }
    }
    
    # 教師マッピング
    teacher_map = {
        ("1年1組", "国"): "寺田",
        ("1年3組", "家"): "金子み",
        ("2年2組", "理"): "智田",
        ("2年3組", "数"): "井上",
        ("3年2組", "保"): "財津",
    }
    
    print("【ステップ1】特会（月曜4限）の違反を修正")
    
    meeting_info = meetings["特会"]
    meeting_day, meeting_period = meeting_info["time"]
    meeting_col = get_cell(meeting_day, meeting_period)
    
    for class_name, subject, teacher in meeting_info["violations"]:
        class_row = get_class_row(class_name)
        if not class_row:
            continue
        
        # 移動先を探す
        moved = False
        for day in ["火", "水", "木", "金"]:
            for period in ["2", "3", "4", "5"]:
                # 会議時間は避ける
                if (day == "火" and period == "3") or \
                   (day == "木" and period in ["2", "3"]) or \
                   (day == "月" and period == "4"):
                    continue
                
                target_col = get_cell(day, period)
                if not target_col:
                    continue
                
                target_subject = df.iloc[class_row, target_col]
                
                # 固定科目でなければ交換
                if not is_fixed_subject(target_subject) and pd.notna(target_subject):
                    df.iloc[class_row, meeting_col] = target_subject
                    df.iloc[class_row, target_col] = subject
                    print(f"  ✓ {class_name}: 月4限({subject}) ⇔ {day}{period}限({target_subject})")
                    moved = True
                    break
            
            if moved:
                break
        
        if not moved:
            print(f"  ✗ {class_name}: 移動先が見つかりません")
    
    print("\n【ステップ2】企画（木曜3限）の違反を修正")
    
    meeting_info = meetings["企画"]
    meeting_day, meeting_period = meeting_info["time"]
    meeting_col = get_cell(meeting_day, meeting_period)
    
    for class_name, subject, teacher in meeting_info["violations"]:
        class_row = get_class_row(class_name)
        if not class_row:
            continue
        
        # 金曜日の空いている時間と交換
        moved = False
        for period in ["2", "3", "4", "5"]:
            target_col = get_cell("金", period)
            if not target_col:
                continue
            
            target_subject = df.iloc[class_row, target_col]
            
            if not is_fixed_subject(target_subject) and pd.notna(target_subject):
                df.iloc[class_row, meeting_col] = target_subject
                df.iloc[class_row, target_col] = subject
                print(f"  ✓ {class_name}: 木3限({subject}) ⇔ 金{period}限({target_subject})")
                moved = True
                break
        
        if not moved:
            print(f"  ✗ {class_name}: 移動先が見つかりません")
    
    # 検証
    print("\n【最終検証】")
    
    # 特会の検証
    print("\n月曜4限（特会）:")
    violations = 0
    for class_name, subject, teacher in meetings["特会"]["violations"]:
        class_row = get_class_row(class_name)
        if class_row:
            current_subject = df.iloc[class_row, get_cell("月", "4")]
            if current_subject == subject:
                print(f"  ❌ {class_name}: まだ{subject}が残っています")
                violations += 1
    
    if violations == 0:
        print("  ✅ すべての違反が解決されました")
    
    # 企画の検証
    print("\n木曜3限（企画）:")
    violations = 0
    for class_name, subject, teacher in meetings["企画"]["violations"]:
        class_row = get_class_row(class_name)
        if class_row:
            current_subject = df.iloc[class_row, get_cell("木", "3")]
            if current_subject == subject:
                print(f"  ❌ {class_name}: まだ{subject}が残っています")
                violations += 1
    
    if violations == 0:
        print("  ✅ すべての違反が解決されました")
    
    # 保存
    df.to_csv(output_path, index=False, header=False)
    print(f"\n修正完了: {output_path}")

if __name__ == "__main__":
    fix_meeting_conflicts()