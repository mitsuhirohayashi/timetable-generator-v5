#!/usr/bin/env python3
"""全ての会議時間の制約チェック"""

import pandas as pd
from pathlib import Path

def parse_followup_for_meetings(followup_path):
    """Follow-up.csvから会議情報を抽出"""
    meetings = []
    
    with open(followup_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    current_day = None
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # 曜日を検出
        if line.endswith("日："):
            current_day = line[0]  # 月、火、水、木、金
            continue
        
        # 会議情報を抽出
        # HF
        if "HF" in line and "校時" in line:
            if "4校時" in line or "4時間目" in line:
                meetings.append(("HF", current_day, 4, "2年団全員"))
        
        # 企画
        if "企画" in line and ("校時" in line or "時間目" in line):
            if "3校時" in line or "3時間目" in line:
                meetings.append(("企画", current_day, 3, "企画委員"))
        
        # 特会（特別活動）
        if "特会" in line and ("校時" in line or "時間目" in line):
            for i in range(1, 7):
                if f"{i}校時" in line or f"{i}時間目" in line:
                    meetings.append(("特会", current_day, i, "特会担当"))
        
        # 生指（生活指導）
        if "生指" in line and ("校時" in line or "時間目" in line):
            for i in range(1, 7):
                if f"{i}校時" in line or f"{i}時間目" in line:
                    meetings.append(("生指", current_day, i, "生指担当"))
        
        # 初研（初任者研修）
        if ("初研" in line or "初任研" in line) and "校時" in line:
            # 例：井野口先生が1・2・3校時に初任研をする
            teacher = None
            periods = []
            
            if "井野口" in line:
                teacher = "井野口"
            
            # 時限を抽出
            import re
            period_matches = re.findall(r'(\d)[・、]*(?:・|、)*(?:\d)*[・、]*(?:・|、)*(?:\d)*校時', line)
            if period_matches:
                for match in period_matches[0]:
                    if match.isdigit():
                        periods.append(int(match))
            
            if teacher and periods:
                for period in periods:
                    meetings.append(("初研", current_day, period, teacher))
    
    return meetings

def check_meetings_violations(csv_path, meetings):
    """会議時間に授業が配置されていないかチェック"""
    df = pd.read_csv(csv_path, header=None)
    
    days = df.iloc[0, 1:].tolist()
    periods = df.iloc[1, 1:].tolist()
    
    violations = []
    
    for meeting_type, day, period, participants in meetings:
        print(f"\n【{meeting_type}】{day}曜{period}限 - 参加者: {participants}")
        
        # その時間のカラムインデックスを見つける
        target_col = None
        for col_idx in range(1, len(df.columns)):
            if days[col_idx - 1] == day and str(periods[col_idx - 1]) == str(period):
                target_col = col_idx
                break
        
        if target_col is None:
            print(f"  ⚠️ {day}曜{period}限が見つかりません")
            continue
        
        # 各クラスの授業をチェック
        class_violations = []
        
        for row_idx in range(2, len(df)):
            class_name = df.iloc[row_idx, 0]
            if pd.isna(class_name) or class_name == "":
                continue
            
            subject = df.iloc[row_idx, target_col]
            if pd.isna(subject) or subject == "" or subject in ["欠", "YT", "道", "学", "総", "行", "学総"]:
                continue
            
            # 会議タイプ別のチェック
            should_check = False
            
            if meeting_type == "HF" and "2年" in class_name:
                should_check = True
            elif meeting_type == "初研" and participants == "井野口":
                # 井野口先生が担当するクラスをチェック（1年1組、1年2組、1年3組の英語など）
                if "1年" in class_name and subject == "英":
                    should_check = True
            elif meeting_type in ["企画", "特会", "生指"]:
                # これらの会議は特定の先生のみが参加するので、
                # より詳細な参加者リストが必要
                pass
            
            if should_check:
                class_violations.append(f"{class_name}: {subject}")
                violations.append({
                    'meeting': meeting_type,
                    'day': day,
                    'period': period,
                    'class': class_name,
                    'subject': subject
                })
        
        if class_violations:
            print(f"  ❌ 違反あり:")
            for v in class_violations:
                print(f"    - {v}")
        else:
            print(f"  ✅ 違反なし")
    
    return violations

def check_all_standard_meetings(csv_path):
    """標準的な会議時間をチェック"""
    print("=== 標準的な会議時間のチェック ===")
    
    standard_meetings = [
        ("HF", "火", 4, "2年団全員"),
        ("企画", "火", 3, "企画委員（通常は管理職＋各学年主任）"),
        ("特会", "水", 2, "特別活動担当"),
        ("生指", "木", 3, "生活指導担当"),
    ]
    
    violations = check_meetings_violations(csv_path, standard_meetings)
    
    return violations

def main():
    """メイン処理"""
    data_dir = Path(__file__).parent / "data"
    csv_path = data_dir / "output" / "output.csv"
    followup_path = data_dir / "input" / "Follow-up.csv"
    
    print("=== 全会議時間の制約チェック ===")
    
    # Follow-up.csvから会議情報を抽出
    print("\n1. Follow-up.csvから会議情報を抽出")
    meetings = parse_followup_for_meetings(followup_path)
    
    print(f"\n抽出された会議: {len(meetings)}件")
    for meeting in meetings:
        print(f"  - {meeting[0]}: {meeting[1]}曜{meeting[2]}限 ({meeting[3]})")
    
    # 会議時間の違反をチェック
    print("\n2. 会議時間の違反チェック")
    violations = check_meetings_violations(csv_path, meetings)
    
    # 標準的な会議時間もチェック
    print("\n3. 標準的な会議時間のチェック")
    standard_violations = check_all_standard_meetings(csv_path)
    
    # 結果サマリー
    print("\n=== チェック結果サマリー ===")
    all_violations = violations + standard_violations
    
    if all_violations:
        print(f"\n❌ 合計{len(all_violations)}件の会議時間違反が見つかりました:")
        
        # 会議タイプ別に集計
        by_meeting = {}
        for v in all_violations:
            meeting = v['meeting']
            if meeting not in by_meeting:
                by_meeting[meeting] = []
            by_meeting[meeting].append(v)
        
        for meeting, vlist in by_meeting.items():
            print(f"\n【{meeting}】{len(vlist)}件")
            for v in vlist:
                print(f"  - {v['day']}曜{v['period']}限: {v['class']} ({v['subject']})")
    else:
        print("\n✅ 会議時間の違反はありませんでした")

if __name__ == "__main__":
    main()