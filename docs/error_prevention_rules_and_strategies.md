# エラー防止のためのルールと戦略

## 概要
本ドキュメントは、時間割生成システムで発生した問題の根本原因と、それらを防ぐための恒久的なルールと戦略をまとめたものです。

## 🚨 最重要ルール - 固定科目の絶対的優先（2025-06-23追加）

### 問題の概要
システムが月曜6限のYTを勝手に欠に変更する重大な問題が発生しました（14件）。

### 根本原因
1. `MondaySixthPeriodConstraint`のデフォルトルール（行85-86）が「欠」を強制
2. `fix_monday_6th_period.py`が自動的にYTを欠に変更
3. システムのルールがinput.csvより優先される設計

### 恒久的ルール
```
【最重要ルール】
input.csvの固定科目（YT、欠、学、総、道、学総、行）は絶対に変更禁止
- システムのデフォルトルールよりもinput.csvが優先
- 制約違反として報告は可だが、修正は不可
- fix_*スクリプトで固定科目を変更してはいけない
```

### 実装上の注意
1. **MondaySixthPeriodConstraintの修正**
   - `respect_input=True`をデフォルトに
   - input.csvの内容を変更しないロジックに修正済み

2. **使用禁止スクリプト**
   - `fix_monday_6th_period.py` - 固定科目を変更するため使用禁止

3. **固定科目リスト**
   - 欠（欠課）
   - YT（特別活動）
   - 学、学活（学級活動）
   - 総、総合（総合的な学習の時間）
   - 道、道徳（道徳）
   - 学総（学年総合）
   - 行、行事（行事）
   - テスト（定期テスト）
   - 技家（技術・家庭科合併テスト）

## 1. 教師不在違反の防止

### 問題の根本原因
1. **データ連携の不整合**
   - `ConstraintValidatorImproved`が期待する`teacher_absences`属性と、`TeacherAbsenceLoader`の`absences`属性の不一致
   - データ形式の相違（Dict形式 vs Set[Tuple]形式）

2. **更新タイミングの問題**
   - Follow-up.csvから読み込んだ教師不在情報が、制約バリデーターに反映されない
   - 初期化時点で空のデータが渡され、後から更新されても反映されない

### 実装された解決策
```python
# TeacherAbsenceLoaderに追加されたプロパティ
@property
def teacher_absences(self) -> Dict[str, Set[Tuple[str, int]]]:
    """ConstraintValidatorが期待する形式で教師不在情報を提供"""
    result = {}
    for day, day_absences in self.absences.items():
        # 終日不在
        for teacher in day_absences.get('all_day', []):
            if teacher not in result:
                result[teacher] = set()
            for period in range(1, 7):
                result[teacher].add((day, period))
        # 時限別不在
        for period, teachers in day_absences.get('periods', {}).items():
            for teacher in teachers:
                if teacher not in result:
                    result[teacher] = set()
                result[teacher].add((day, period))
    return result
```

### 恒久的ルール
1. **データインターフェースの標準化**
   - すべてのデータ交換は明確なインターフェースを定義する
   - 属性名とデータ形式を統一する
   - 後方互換性を保つため、必要に応じてアダプターパターンを使用

2. **データ更新の即時反映**
   - Follow-up.csvからの読み込み後、すべての依存コンポーネントに通知
   - プッシュ型の更新メカニズムを実装

## 2. 交流学級の自立活動違反の防止

### 問題の根本原因
- **双方向チェックの欠如**
  - 交流学級に自立活動を配置する際、親学級の科目チェックが不十分
  - 親学級の科目を変更する際、交流学級が自立活動かどうかのチェックが欠落

### 実装された解決策
```python
# ExchangeClassServiceに追加されたメソッド

def can_place_jiritsu_for_exchange_class(self, schedule, time_slot, exchange_class) -> bool:
    """交流学級に自立活動を配置可能かチェック"""
    parent_class = self.get_parent_class(exchange_class)
    parent_assignment = schedule.get_assignment(time_slot, parent_class)
    
    # 親学級が数学・英語でない場合は配置不可
    if not parent_assignment or parent_assignment.subject.name not in ["数", "英", "算"]:
        return False
    return True

def can_change_parent_class_subject(self, schedule, time_slot, parent_class, new_subject) -> bool:
    """親学級の科目を変更可能かチェック"""
    exchange_class = self.get_exchange_class(parent_class)
    exchange_assignment = schedule.get_assignment(time_slot, exchange_class)
    
    # 交流学級が自立活動で、新科目が数学・英語でない場合は変更不可
    if exchange_assignment and is_jiritsu_activity(exchange_assignment.subject.name):
        if new_subject.name not in ["数", "英", "算"]:
            return False
    return True
```

### 恒久的ルール
1. **双方向チェックの徹底**
   - 関連するエンティティを変更する際は、必ず双方向でチェック
   - 親学級⇔交流学級、教師⇔クラスなど、相互に影響する要素は必ず両方向から検証

2. **事前検証の強化**
   - 配置前に必ず制約チェックを実行
   - 違反の可能性がある場合は配置を阻止

## 3. 日内重複の防止

### 問題の根本原因
- **キャッシュの不適切な管理**
  - `ConstraintValidatorImproved`のキャッシュが古い情報を保持
  - スケジュール更新時にキャッシュがクリアされない

### 恒久的ルール
1. **キャッシュの適切な無効化**
   ```python
   # スケジュール更新時は必ずキャッシュをクリア
   def update_schedule(schedule, time_slot, class_ref, assignment):
       schedule.assign(time_slot, class_ref, assignment)
       constraint_validator.clear_cache()
   ```

2. **キャッシュの有効期限管理**
   - キャッシュには必ず有効期限を設定
   - スケジュール変更イベントで自動的にキャッシュをクリア

## 4. システム全体の品質向上戦略

### ロギングとモニタリング
1. **詳細なログ出力**
   - 制約違反発生時の完全なコンテキストを記録
   - 違反の原因となった具体的なデータを含める

2. **違反パターンの分析**
   - 頻繁に発生する違反パターンを特定
   - 自動的に学習ルールとして取り込む

### テストとバリデーション
1. **単体テストの充実**
   - 各制約チェックのエッジケースをカバー
   - データ連携部分の統合テスト

2. **回帰テストの自動化**
   - 過去に発生した問題が再発しないことを確認
   - CI/CDパイプラインに組み込む

### コード品質の維持
1. **DRY原則の徹底**
   - 共通ロジックは必ずユーティリティクラスに抽出
   - 重複コードを定期的に検出・除去

2. **インターフェースの明確化**
   - 各コンポーネント間の責任境界を明確に定義
   - 依存性注入を活用した疎結合な設計

## 5. 運用上の注意事項

### デプロイ時のチェックリスト
1. Follow-up.csvの形式が正しいか確認
2. teacher_subject_mapping.csvに全教師が登録されているか確認
3. 交流学級と親学級のマッピングが正しいか確認

### トラブルシューティング
1. **教師不在違反が発生した場合**
   - Follow-up.csvの記載内容を確認
   - TeacherAbsenceLoaderのログを確認
   - ConstraintValidatorに正しくデータが渡されているか確認

2. **交流学級違反が発生した場合**
   - 親学級と交流学級の時間割を並べて確認
   - 自立活動の配置時間帯を特定
   - 親学級の科目が数学・英語であることを確認

3. **日内重複が発生した場合**
   - 該当クラスの1日の時間割を確認
   - キャッシュがクリアされているか確認
   - 配置順序に問題がないか確認

## まとめ
これらのルールと戦略を遵守することで、時間割生成システムの品質と信頼性を大幅に向上させることができます。新機能の追加や修正を行う際は、必ずこのドキュメントを参照し、既存のルールに従って実装してください。