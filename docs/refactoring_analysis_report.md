# Comprehensive Refactoring Analysis Report

## Executive Summary

The timetable_v5 project has grown to an unsustainable size with **502 Python files** (244 in src/, 221 in scripts/, 35 in tests/, 2 in root). The codebase shows signs of rapid iterative development with multiple versions of generators, duplicate functionality, and architectural violations. This report provides a detailed analysis and actionable refactoring plan.

## 1. Current State Analysis

### 1.1 File Distribution
```
Directory       | Python Files | Status
----------------|--------------|--------
src/            | 244          | Overly complex structure
scripts/        | 221          | Many duplicates and obsolete files
tests/          | 35           | Poor naming convention, version-specific tests
root/           | 2            | Correct (main.py, setup.py)
Total           | 502          | Needs significant reduction
```

### 1.2 Untracked Files
- **130+ untracked files** including:
  - Multiple backup configurations
  - Numerous analysis reports
  - Archive directories
  - Documentation files scattered across directories

### 1.3 Major Problem Areas

#### A. Generator Version Proliferation
- **22 different generator versions** found (v2-v14, plus variants)
- 18 in archive/old_generators/
- 4 active versions still in src/
- Each generator is 700-1200 lines

#### B. Duplicate Analysis Scripts
- **25+ analyze_*.py scripts** with overlapping functionality
- **15+ check_*.py scripts** with similar purposes
- Many scripts doing the same validation with slight variations

#### C. Oversized Files (>500 lines)
Top offenders:
1. hybrid_schedule_generator_v8.py (1282 lines)
2. schedule_generation_service.py (1079 lines)
3. parallel_optimization_engine.py (1059 lines)
4. teacher_preference_learning_system.py (1028 lines)
5. intelligent_schedule_optimizer.py (1022 lines)

#### `TeacherConflictConstraintRefactored.validate` (120行)
**問題**:
- ネストが深い（最大5レベル）
- デバッグ出力とビジネスロジックが混在
- 火曜5校時の特別処理がハードコーディング

**リファクタリング提案**:
```python
def validate(self, schedule, school):
    violations = []
    for time_slot in self.iterate_all_time_slots():
        violations.extend(self._check_time_slot_conflicts(time_slot, schedule))
    return self._create_result(violations)

def _check_time_slot_conflicts(self, time_slot, schedule):
    teacher_assignments = self._group_by_teacher(schedule.get_assignments_by_time_slot(time_slot))
    return self._find_conflicts(teacher_assignments, time_slot)
```

### 循環的複雑度が高いメソッド

#### `SmartEmptySlotFiller.fill_empty_slots`
- 多くの条件分岐とネストしたループ
- 戦略パターンが部分的にしか適用されていない

## 3. 責任の分離問題

### CSVRepositoryの問題
**現状**: ファサードパターンで改善されているが、まだ多くの責任を持つ
- スケジュール読み込み/書き込み
- 教師スケジュール管理
- 教師不在情報
- 制約情報の管理

**提案**: さらなる分離は不要（既にリファクタリング済み）

### ConstraintManager vs UnifiedConstraintSystem
**問題**: 2つのシステムが並存し、役割が不明確
- どちらも制約を管理
- 統一的なインターフェースが欠如

**リファクタリング提案**: 
- UnifiedConstraintSystemに統一
- ConstraintManagerは廃止または軽量なプロキシとして実装

## 4. 未使用コードの検出

### 削除されたがインポートが残っている可能性
- `src/domain/constraints/consolidated/`ディレクトリが削除済み
- 関連するインポートは見つからず（問題なし）

### 潜在的な未使用モジュール
- `human_like_scheduler.py` (539行) - 使用されているか要確認
- 多数の`*_refactored.py`ファイル - 元のファイルとの関係を整理

## 5. アーキテクチャの問題

### 層間依存の違反（重大）
**問題**: ドメイン層がインフラ層に依存している箇所が19ファイル存在

例:
- `src/domain/services/csp_orchestrator.py`が`infrastructure.config`をインポート
- `src/domain/constraints/`の複数ファイルがインフラ層に依存

**リファクタリング提案**:
1. 設定インターフェースをドメイン層に定義
```python
# domain/interfaces/config.py
class ICSPConfig(ABC):
    @abstractmethod
    def get_max_iterations(self) -> int:
        pass
```

2. インフラ層で実装
```python
# infrastructure/config/csp_config.py
class CSPConfig(ICSPConfig):
    def get_max_iterations(self) -> int:
        return self._config.get('max_iterations', 100)
```

### 抽象化の不足
- 多くのサービスクラスが具象実装に直接依存
- インターフェースの定義が不十分

## 6. 命名とコードスタイル

### 一貫性のない命名
- 日本語と英語の混在（例: `teacher_conflict_constraint_refactored.py`）
- `_refactored`サフィックスの使用（技術的詳細が名前に含まれる）

### マジックナンバー
- 曜日のリスト: `["月", "火", "水", "木", "金"]`
- 時限の範囲: `range(1, 7)`
- 優先度の数値: `100`, `80`, `60`, `40`, `20`

**リファクタリング提案**:
```python
# constants.py
WEEKDAYS = ["月", "火", "水", "木", "金"]
PERIODS = range(1, 7)
MAX_PERIODS = 6
```

## 7. エラーハンドリングとテスト

### 不一貫なエラーハンドリング
- try-exceptでエラーを握りつぶしている箇所
- ログ出力のみで例外を再発生させない

例（generate_schedule.py 268行目）:
```python
except:
    pass  # エラーを無視
```

### テストカバレッジの不足
- ドメインサービスの複雑なロジックに対するユニットテストが不足
- 統合テストが主体で、単体テストが少ない

## 優先度の高いリファクタリング項目

1. **層間依存の解消**（優先度: CRITICAL）
   - ドメイン層からインフラ層への依存を除去
   - 依存性逆転の原則を適用

2. **複雑なメソッドの分割**（優先度: HIGH）
   - 100行を超えるメソッドを30行以下に分割
   - 単一責任原則の適用

3. **共通定数の抽出**（優先度: MEDIUM）
   - マジックナンバーと文字列の定数化
   - 設定ファイルへの外部化

4. **エラーハンドリングの統一**（優先度: MEDIUM）
   - 一貫したエラー処理ポリシーの確立
   - カスタム例外クラスの定義

5. **命名の統一**（優先度: LOW）
   - `_refactored`サフィックスの除去
   - 一貫した命名規則の適用