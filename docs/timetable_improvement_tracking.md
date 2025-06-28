# 時間割生成改善追跡ガイド

## 一進一退を防ぐための改善プロセス

### 1. ベースライン設定
現在の状態を正確に記録し、改善の基準点とする：

```bash
# 現状の記録
python3 scripts/utilities/diagnostic_report.py
cp diagnostic_report.json baseline_report.json
cp data/output/output.csv data/output/baseline.csv
```

### 2. 段階的改善アプローチ

#### Phase 1: 実現可能性の確保（1-2日）
```bash
# 制約の実現可能性チェック
python3 scripts/utilities/constraint_feasibility_checker.py

# 問題がある場合は制約を調整
# - 教師の追加割り当て
# - 固定科目の見直し
# - 必要時数の調整
```

#### Phase 2: 基本制約での生成（3-4日）
```bash
# 最小限の制約で生成
python3 main.py generate --minimal-constraints

# 結果を確認
python3 check_violations.py > phase2_violations.txt
```

#### Phase 3: 制約の段階的追加（5-7日）
```bash
# 段階的制約緩和システムを使用
python3 scripts/utilities/progressive_constraint_relaxation.py

# 最適レベルで再生成
python3 main.py generate --constraint-level 2
```

#### Phase 4: 細かい調整（8-10日）
```bash
# 個別の違反を修正
python3 main.py fix --fix-teacher-conflicts
python3 main.py fix --fix-exchange-sync
```

### 3. 改善の測定指標

各フェーズで以下を記録：

| 指標 | 目標値 | 測定方法 |
|------|--------|----------|
| 総違反数 | < 10件 | `check_violations.py` |
| 教師重複 | 0件 | 診断レポート |
| 5組同期 | 100% | 診断レポート |
| 生成時間 | < 30秒 | タイマー計測 |
| 空きコマ | < 5% | `find_empty_slots.py` |

### 4. トラブルシューティング

#### 問題: 教師重複が減らない
```bash
# 教師負荷分析
python3 scripts/analysis/analyze_teacher_workload.py

# 5組を優先配置
python3 scripts/fixes/prioritize_grade5_placement.py
```

#### 問題: 制約違反が増える
```bash
# 制約の依存関係を確認
python3 scripts/utilities/constraint_feasibility_checker.py

# 競合する制約を特定して優先度調整
```

#### 問題: 生成が失敗する
```bash
# 段階的緩和で実現可能解を探索
python3 scripts/utilities/progressive_constraint_relaxation.py

# 最小構成から再構築
```

### 5. 成功パターンの記録

改善が成功したら必ず記録：

```bash
# 成功した設定を保存
cp data/output/output.csv data/output/success_$(date +%Y%m%d).csv
cp diagnostic_report.json success_reports/report_$(date +%Y%m%d).json

# QandAシステムに記録
echo "成功パターン: [詳細をここに記載]" >> QandA/success_patterns.txt
```

### 6. 継続的改善サイクル

1. **月次レビュー**: 蓄積されたデータから傾向分析
2. **制約の最適化**: 実績に基づいて制約優先度を調整
3. **アルゴリズム改善**: 頻出する問題パターンへの対策実装

## まとめ

一進一退を防ぐ鍵は：
- **測定可能な指標**での進捗管理
- **段階的アプローチ**による着実な改善
- **成功パターンの記録**と再利用
- **制約の実現可能性**の事前確認

このプロセスに従うことで、確実に時間割生成の精度を向上させることができます。