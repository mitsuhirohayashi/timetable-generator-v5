# 統一ハイブリッド戦略V2への共有日内科目追跡の実装

## 実装日
2025-06-24

## 背景
統一ハイブリッド戦略V2では、各配置フェーズ（主要教科、技能教科、空きスロット埋め）が独立して日内科目を追跡していたため、18件の日内重複違反が発生していました。

## 問題の原因
1. **独立した追跡**: 各メソッドが独自の`daily_subjects`変数を使用
2. **技能教科での欠如**: `_place_skill_subjects_improved`に日内重複チェックがなかった
3. **情報の非共有**: 前のフェーズで配置された科目を後のフェーズが認識できない

## 実装内容

### 1. 共有追跡システムの追加
```python
def __init__(self, constraint_system):
    super().__init__(constraint_system)
    self.shared_daily_subjects = defaultdict(set)  # 全フェーズで共有
```

### 2. 初期化時の追跡登録
`_protect_and_initialize`メソッドで既存の配置を共有追跡に登録：
```python
class_key = f"{class_ref.grade}年{class_ref.class_number}組"
self.shared_daily_subjects[(class_key, day)].add(assignment.subject.name)
```

### 3. 各フェーズでの共有追跡使用

#### _place_major_subjects_improved
- 日内重複チェック: `if subject in self.shared_daily_subjects[(class_key, day)]:`
- 配置後の追跡: `self.shared_daily_subjects[(class_key, day)].add(subject)`

#### _place_skill_subjects_improved（新規追加）
- 日内重複チェックを追加
- 配置後の追跡を追加

#### _fill_empty_slots
- ローカルの`daily_subjects`を削除
- 共有追跡を使用するよう変更

## 期待される効果
- 日内重複違反を18件から大幅に削減
- 全フェーズで一貫した科目管理
- より質の高い時間割の生成

## 技術的詳細
共有追跡システムは`defaultdict(set)`を使用し、キーは`(class_key, day)`のタプルです。これにより、各クラス・各曜日の配置済み科目を効率的に管理できます。

## テスト方法
```bash
python scripts/tests/test_v2_shared_tracking.py
```

このテストスクリプトは：
1. V2戦略で時間割を生成
2. 日内重複違反をチェック
3. 改善前後の違反数を比較
4. 結果をレポート

## 注意事項
- 5組の合同授業（1-5, 2-5, 3-5）は3クラスで同じ科目を配置するため、日内重複とは見なされません
- 交流学級（6組、7組）と親学級の同一科目配置も正常な運用です
- テスト期間中の巡回監督による重複も制約違反ではありません