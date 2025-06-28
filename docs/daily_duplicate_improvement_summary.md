# 日内重複改善の取り組み

## 問題の分析

統一ハイブリッド戦略V2で18件の日内重複が発生する原因を分析した結果、以下の問題が判明しました：

1. **フェーズごとの独立追跡**: 各配置フェーズ（主要教科、技能教科、空きスロット埋め）が独自に日内科目を追跡
2. **技能教科の重複チェック欠如**: `_place_skill_subjects_improved`メソッドで日内重複チェックが未実装
3. **既存配置の見落とし**: 後のフェーズが前のフェーズで配置された科目を認識できない

## V3の実装試行

全フェーズで共有される`DailySubjectTracker`クラスを実装したV3を作成しましたが、以下の互換性問題が発生：

- `get_teacher_by_name`メソッドの不在
- `clear_slot`メソッドの不在
- その他のインターフェース不整合

## 推奨される改善策

V2に最小限の変更を加えることで日内重複を削減：

### 1. 共有日内追跡の追加
```python
class UnifiedHybridStrategyV2(BaseGenerationStrategy):
    def __init__(self, constraint_system):
        super().__init__(constraint_system)
        self.daily_subjects = defaultdict(set)  # 全フェーズで共有
```

### 2. 技能教科配置での重複チェック追加
```python
def _place_skill_subjects_improved(self, schedule, school):
    # ...
    for subject in skill_subjects:
        # 日内重複チェック
        if subject in self.daily_subjects[(class_key, day)]:
            continue
        # ...
```

### 3. 各配置後の追跡更新
```python
# 配置成功後
self.daily_subjects[(class_key, day)].add(subject)
```

## 現在の違反状況（V2）

【日内重複制約違反】18件
- 1年1組の月曜日に国が2回
- 1年1組の火曜日に数が2回
- 1年1組の金曜日に英が2回
- 1年2組の金曜日に国が2回
- 1年3組の火曜日に数が2回
- 他13件

## 期待される効果

- 日内重複違反を18件から大幅に削減
- 特に技能教科の重複配置を防止
- 全フェーズで一貫した日内科目管理

## 結論

V3の完全な実装よりも、V2への最小限の変更により、リスクを抑えながら日内重複問題を改善できます。共有日内追跡システムの実装により、現在の18件の日内重複を大幅に削減できることが期待されます。