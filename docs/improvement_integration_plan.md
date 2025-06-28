# 時間割生成システム改善統合計画

## 概要

現在の制約違反（118件）を20件以下に削減するための改善策を、既存システムに段階的に統合する計画書です。

## 現状分析

### 主要な問題
1. **5組同期違反**: 100件（84.7%）
   - 原因: 5組を個別に配置してから同期を試みている
   - 影響: 教師リソースの無駄遣い、制約充足の困難化

2. **教師重複**: 18件（15.3%）
   - 原因: 配置時に教師の可用性チェックが不十分
   - 影響: 物理的に不可能な時間割

## 改善策の実装

### Phase 1: 5組優先配置（実装済み）

**ファイル**: `src/domain/services/grade5_priority_placement_service.py`

**特徴**:
- 5組（1年5組、2年5組、3年5組）を最初に一括配置
- 金子み先生を5組専任として優先活用
- 固定スロット（欠、YT、テスト）を自動識別して回避

**期待効果**: 5組同期違反 100件 → 0件

### Phase 2: 改善版CSP生成器（実装済み）

**ファイル**: `src/domain/services/implementations/improved_csp_generator.py`

**特徴**:
- 4段階の配置戦略
- 教師スケジュールのリアルタイム追跡
- バックトラッキングによる競合解決

**期待効果**: 教師重複 18件 → 5件以下

## 統合手順

### Step 1: ScheduleGenerationServiceへの統合

```python
# src/application/services/schedule_generation_service.py に追加

def generate_schedule_improved(self, ...):
    """改善版アルゴリズムでの生成"""
    from ...domain.services.implementations.improved_csp_generator import ImprovedCSPGenerator
    
    generator = ImprovedCSPGenerator(self.constraint_system)
    schedule = generator.generate(
        school=school,
        initial_schedule=initial_schedule,
        followup_constraints=followup_constraints
    )
    
    return schedule
```

### Step 2: CLIオプションの追加

```python
# src/presentation/cli/main.py に追加

parser.add_argument(
    '--use-improved',
    action='store_true',
    help='改善版アルゴリズムを使用（5組優先配置）'
)
```

### Step 3: 段階的テスト計画

#### 3.1 単体テスト
```bash
# 5組優先配置のみテスト
python3 test_grade5_priority_placement.py

# 教師追跡機能テスト
python3 test_teacher_tracking.py
```

#### 3.2 統合テスト
```bash
# 改善版で生成
python3 main.py generate --use-improved

# 違反チェック
python3 scripts/analysis/check_violations.py

# 比較分析
python3 compare_results.py
```

## リスク管理

### 潜在的リスク
1. **互換性問題**: 既存の制約システムとの統合
2. **パフォーマンス**: 追加処理による生成時間増加
3. **エッジケース**: 特殊な制約条件での動作

### 対策
1. **段階的導入**: オプションフラグで切り替え可能に
2. **ロールバック**: 従来版アルゴリズムを維持
3. **詳細ログ**: デバッグ用の統計情報出力

## 成功指標

| 指標 | 現在 | 目標 | 改善率 |
|------|------|------|--------|
| 総違反数 | 118件 | 20件以下 | 83%削減 |
| 5組同期違反 | 100件 | 0件 | 100%解決 |
| 教師重複 | 18件 | 5件以下 | 72%削減 |
| 生成時間 | - | 30秒以内 | - |

## タイムライン

1. **Week 1**: 既存システムへの統合
   - ScheduleGenerationServiceの拡張
   - CLIオプションの追加

2. **Week 2**: テストと検証
   - 単体テストの実施
   - 統合テストの実施
   - パフォーマンス測定

3. **Week 3**: 最適化と調整
   - パラメータチューニング
   - エッジケースの対応
   - ドキュメント更新

4. **Week 4**: 本番導入
   - 段階的ロールアウト
   - モニタリング
   - フィードバック収集

## まとめ

この統合計画により、時間割生成の精度を大幅に向上させることができます。特に：

- **5組同期違反の完全解決**により、最大の問題を根本から解消
- **教師リソースの効率化**により、実現可能な時間割生成を保証
- **段階的な統合**により、リスクを最小化しながら改善を実現

既存システムとの互換性を保ちながら、確実な改善効果を得ることができます。