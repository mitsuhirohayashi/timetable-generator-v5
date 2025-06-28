# Phase 2 リファクタリング - 移行計画

## 概要
Phase 2「データクラスとビジネスロジックの分離」では、ドメインエンティティからビジネスロジックを分離し、データ保持に特化したクラスとビジネスロジックを提供するサービスクラスに分割しました。

## 実施内容

### 1. 新規作成したクラス

#### データ保持クラス
- `ScheduleData` - 時間割の純粋なデータ
- `SchoolData` - 学校の純粋なデータ
- `Grade5UnitData` - 5組ユニットの純粋なデータ

#### ビジネスロジックサービス
- `ScheduleBusinessService` - スケジュールのビジネスロジック
- `SchoolBusinessService` - 学校のビジネスロジック
- `Grade5UnitBusinessService` - 5組ユニットのビジネスロジック
- `ViolationCollector` - 制約違反の収集・管理

#### リファクタリング版エンティティ（ファサード）
- `schedule_refactored.py` - 既存インターフェースを維持したファサード
- `school_refactored.py` - 既存インターフェースを維持したファサード

### 2. 分離したビジネスロジック

#### Scheduleエンティティから分離
- 5組の同期処理 → `ScheduleBusinessService.assign_with_grade5_sync()`
- 教師の利用可能性チェック → `ScheduleBusinessService.is_teacher_available()`
- 日内重複チェック → `ScheduleBusinessService.has_daily_duplicate()`
- 空きスロット計算 → `ScheduleBusinessService.get_empty_slots()`

#### Schoolエンティティから分離
- 設定の妥当性検証 → `SchoolBusinessService.validate_setup()`
- 教師の負荷分析 → `SchoolBusinessService.get_teacher_workload_summary()`
- クラスタイプ別フィルタ → `SchoolBusinessService.get_classes_by_type()`

#### Grade5Unitエンティティから分離
- 配置可能性チェック → `Grade5UnitBusinessService.can_assign()`
- 時数表記処理 → `Grade5UnitBusinessService.create_assignment_with_hour_notation()`
- 時数配分最適化 → `Grade5UnitBusinessService.optimize_hour_distribution()`

### 3. 移行戦略

#### Step 1: 並行実装期間（推奨）
1. 既存のエンティティ（schedule.py, school.py, grade5_unit.py）を維持
2. 新しいリファクタリング版（_refactored.py）を並行して配置
3. 新規開発では新しい実装を使用

#### Step 2: 段階的切り替え
1. 単体テストから新しい実装に切り替え
2. サービスクラスから順次切り替え
3. 制約クラスを新しい実装に対応

#### Step 3: 完全移行
1. 古い実装への参照を全て更新
2. 古いファイルを削除またはアーカイブ
3. _refactoredサフィックスを削除

## 実装例

### 新しい使い方（推奨）
```python
# データとビジネスロジックを明確に分離
from domain.entities.schedule_data import ScheduleData
from domain.services.schedule_business_service import ScheduleBusinessService

# データ操作
data = ScheduleData()
data.set_assignment(time_slot, class_ref, assignment)

# ビジネスロジック
service = ScheduleBusinessService()
if service.is_teacher_available(data, time_slot, teacher):
    service.assign_with_grade5_sync(data, grade5_unit, time_slot, assignment)
```

### 既存互換性を保った使い方
```python
# 従来通りのインターフェース
from domain.entities.schedule_refactored import Schedule

schedule = Schedule()
schedule.assign(time_slot, assignment)  # 内部で自動的に処理
```

## メリット

1. **単一責任原則**: 各クラスが明確な責任を持つ
2. **テスタビリティ**: ビジネスロジックを独立してテスト可能
3. **保守性**: データ構造の変更とビジネスルールの変更が独立
4. **拡張性**: 新しいビジネスロジックを追加しやすい

## 注意事項

1. **パフォーマンス**: ファサードパターンによる若干のオーバーヘッド
2. **複雑性**: クラス数が増加（ただし各クラスはシンプル）
3. **移行期間**: 新旧の実装が混在する期間の管理

## 次のステップ

1. **制約クラスの更新**: 新しいデータ/サービス構造を使用するよう更新
2. **DIコンテナの拡張**: 新しいサービスクラスの登録
3. **統合テスト**: 新しい実装での完全なテスト実施