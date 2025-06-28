#!/usr/bin/env python3
"""交流学級同期問題の簡易調査スクリプト"""

import csv

def main():
    # CSVファイルを直接読み込む
    output_path = "data/output/output.csv"
    
    with open(output_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        rows = list(reader)
    
    # ヘッダー行を解析
    days = rows[0][1:]  # 曜日
    periods = rows[1][1:]  # 時限
    
    # 3年3組と3年6組のデータを探す
    class_3_3_data = None
    class_3_6_data = None
    
    for i, row in enumerate(rows[2:], 2):
        if row[0] == "3年3組":
            class_3_3_data = (i, row[1:])
        elif row[0] == "3年6組":
            class_3_6_data = (i, row[1:])
    
    if not class_3_3_data or not class_3_6_data:
        print("3年3組または3年6組のデータが見つかりません")
        return
    
    print("=== 交流学級同期問題の調査 ===")
    print()
    
    # 問題箇所の詳細を表示
    sync_violations = []
    daily_duplicates = {"月": {}, "火": {}, "水": {}, "木": {}, "金": {}}
    
    for i, (day, period) in enumerate(zip(days, periods)):
        subject_3_3 = class_3_3_data[1][i] if i < len(class_3_3_data[1]) else ""
        subject_3_6 = class_3_6_data[1][i] if i < len(class_3_6_data[1]) else ""
        
        # 空白を（空き）に変換
        if not subject_3_3:
            subject_3_3 = "（空き）"
        if not subject_3_6:
            subject_3_6 = "（空き）"
        
        # 日内重複チェック（3年3組）
        if subject_3_3 != "（空き）" and subject_3_3 not in ["欠", "YT", "学", "総", "道", "学総", "行", "技家", "保"]:
            if subject_3_3 not in daily_duplicates[day]:
                daily_duplicates[day][subject_3_3] = []
            daily_duplicates[day][subject_3_3].append(period)
        
        # 同期違反チェック
        if subject_3_6 == "自立":
            if subject_3_3 not in ["数", "英"]:
                sync_violations.append((day, period, subject_3_3, subject_3_6, "自立違反"))
        elif subject_3_3 != subject_3_6 and not (subject_3_3 == "（空き）" and subject_3_6 == "（空き）"):
            sync_violations.append((day, period, subject_3_3, subject_3_6, "同期違反"))
    
    # 違反の表示
    print("【交流学級同期違反】")
    for day, period, s3_3, s3_6, vtype in sync_violations:
        print(f"  {day}曜{period}限: 3年3組={s3_3}, 3年6組={s3_6} ({vtype})")
    
    print("\n【日内重複違反（3年3組）】")
    for day, subjects in daily_duplicates.items():
        for subject, periods in subjects.items():
            if len(periods) > 1:
                print(f"  {day}曜日: {subject}が{len(periods)}回 ({', '.join(periods)}限)")
    
    # 問題の分析
    print("\n=== 問題の分析 ===")
    print("\n1. 交流学級同期の問題:")
    print("  - 木曜2限: 3年3組=保、3年6組=（空き）")
    print("  - 金曜5限: 3年3組=保、3年6組=（空き）")
    print("  → 3年6組が親学級と同期していない")
    
    print("\n2. 日内重複の問題:")
    print("  - 月曜日: 英語が4限と6限に重複")
    print("  → 日内重複制約が正しく機能していない")
    
    print("\n=== 推定される根本原因 ===")
    print("\n1. ExchangeClassServiceの validate_exchange_sync メソッド:")
    print("   - 自立活動以外の通常授業の同期をチェックしていない")
    print("   - そのため、保健体育などの通常授業で同期が保証されない")
    
    print("\n2. DailyDuplicateConstraintの _get_max_allowed メソッド:")
    print("   - 主要教科（英語含む）に1日2回まで許可している")
    print("   - CLAUDE.mdの「1日1コマ制限」と矛盾")
    
    print("\n3. 生成時の問題:")
    print("   - 交流学級への配置時に親学級との同期を考慮していない")
    print("   - 空きスロット埋めで交流学級の同期が考慮されていない可能性")

if __name__ == "__main__":
    main()