"""リソース使用制約 - 体育館、特別教室などの共有リソースの管理"""
from typing import Dict, Set, List, Tuple, Optional
from dataclasses import dataclass, field
from collections import defaultdict
from pathlib import Path
import csv
import json

from .base import (
    ConfigurableConstraint, ConstraintConfig, ConstraintType,
    ConstraintPriority, ValidationContext, ConstraintResult, ConstraintViolation
)
from ...value_objects.time_slot import TimeSlot, ClassReference
from ....infrastructure.config.path_config import path_config


@dataclass
class Resource:
    """共有リソース"""
    name: str
    capacity: int  # 同時使用可能数
    subjects: Set[str]  # このリソースを使用する教科
    joint_sessions: List[Set[ClassReference]] = field(default_factory=list)  # 合同授業グループ


@dataclass
class ResourceUsage:
    """リソース使用情報"""
    resource_name: str
    time_slot: TimeSlot
    classes: Set[ClassReference]
    subject: str


class ResourceUsageConstraint(ConfigurableConstraint):
    """リソース使用統合制約
    
    以下の制約を統合:
    - GymUsageConstraintRefactored: 体育館使用制約
    - 将来的に追加可能：音楽室、理科室、コンピュータ室など
    """
    
    def __init__(self):
        config = ConstraintConfig(
            name="リソース使用制約",
            description="体育館、特別教室など共有リソースの使用制限を管理",
            type=ConstraintType.HARD,
            priority=ConstraintPriority.HIGH
        )
        super().__init__(config)
        
        # リソース定義
        self.resources: Dict[str, Resource] = {}
        
        # 時間ごとのリソース使用状況
        self.resource_usage: Dict[Tuple[str, TimeSlot], List[ResourceUsage]] = defaultdict(list)
        
    def _load_configuration(self):
        """設定を読み込む"""
        self._load_gym_configuration()
        self._load_special_rooms()
        self._load_joint_sessions()
        
    def _load_gym_configuration(self):
        """体育館の設定を読み込む"""
        gym = Resource(
            name="体育館",
            capacity=1,  # 同時に1グループのみ
            subjects={"体", "保体", "保健体育"}
        )
        
        # 合同体育の設定を読み込む
        team_teaching_config_path = path_config.config_dir / "team_teaching_config.json"
        if team_teaching_config_path.exists():
            try:
                with open(team_teaching_config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    
                    # 合同体育のグループを抽出
                    if "joint_pe_groups" in config:
                        for group in config["joint_pe_groups"]:
                            classes = set()
                            for class_str in group:
                                # "1-6" -> ClassReference(1, 6)
                                parts = class_str.split('-')
                                if len(parts) == 2:
                                    grade = int(parts[0])
                                    class_num = int(parts[1])
                                    classes.add(ClassReference(grade, class_num))
                            if classes:
                                gym.joint_sessions.append(classes)
                                
            except Exception as e:
                self.logger.warning(f"チームティーチング設定の読み込みエラー: {e}")
        
        # デフォルトの合同体育グループ
        if not gym.joint_sessions:
            # 6組と7組は合同体育
            gym.joint_sessions = [
                {ClassReference(1, 6), ClassReference(1, 7)},
                {ClassReference(2, 6), ClassReference(2, 7)},
                {ClassReference(3, 6), ClassReference(3, 7)}
            ]
        
        self.resources["体育館"] = gym
        
    def _load_special_rooms(self):
        """特別教室の設定を読み込む"""
        special_rooms_path = path_config.config_dir / "special_rooms.csv"
        if special_rooms_path.exists():
            try:
                with open(special_rooms_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        room_name = row.get('教室名', '')
                        capacity = int(row.get('収容数', 1))
                        subjects = set(row.get('使用教科', '').split('、'))
                        
                        if room_name and subjects:
                            self.resources[room_name] = Resource(
                                name=room_name,
                                capacity=capacity,
                                subjects=subjects
                            )
                            
            except Exception as e:
                self.logger.warning(f"特別教室設定の読み込みエラー: {e}")
        
        # デフォルトの特別教室（必要に応じて）
        # self.resources["音楽室"] = Resource(name="音楽室", capacity=1, subjects={"音", "音楽"})
        # self.resources["理科室"] = Resource(name="理科室", capacity=1, subjects={"理", "理科"})
        
    def _load_joint_sessions(self):
        """合同授業の設定を読み込む"""
        # 既に体育館の設定で読み込み済み
        # 他のリソースの合同授業設定があればここで読み込む
        pass
        
    def validate(self, context: ValidationContext) -> ConstraintResult:
        """制約を検証する"""
        result = ConstraintResult(constraint_name=self.name)
        
        # 各リソースについて検証
        for resource_name, resource in self.resources.items():
            self._validate_resource_usage(context, result, resource)
            
        return result
        
    def _validate_resource_usage(self, context: ValidationContext, result: ConstraintResult, resource: Resource):
        """特定リソースの使用を検証"""
        # 時間ごとの使用状況を収集
        usage_by_time = defaultdict(list)
        
        for time_slot in context.schedule.all_time_slots:
            assignments = context.get_assignments_by_time(time_slot)
            
            for assignment in assignments:
                if assignment.subject and assignment.subject.name in resource.subjects:
                    usage_by_time[time_slot].append(assignment)
        
        # 各時間の使用状況をチェック
        for time_slot, assignments in usage_by_time.items():
            if not assignments:
                continue
                
            # 合同授業グループを考慮した使用グループを特定
            usage_groups = self._identify_usage_groups(assignments, resource)
            
            # キャパシティを超えているかチェック
            if len(usage_groups) > resource.capacity:
                # 違反を生成
                group_details = []
                for group in usage_groups:
                    classes = [str(a.class_ref) for a in group]
                    group_details.append(f"[{', '.join(classes)}]")
                
                violation = ConstraintViolation(
                    constraint_name=self.name,
                    severity="ERROR",
                    message=f"{resource.name}が{time_slot}に{len(usage_groups)}グループで使用されています（上限: {resource.capacity}）: {', '.join(group_details)}",
                    time_slot=time_slot
                )
                result.add_violation(violation)
                
    def _identify_usage_groups(self, assignments: List, resource: Resource) -> List[List]:
        """使用グループを特定（合同授業を考慮）"""
        groups = []
        processed = set()
        
        for assignment in assignments:
            if assignment.class_ref in processed:
                continue
                
            # 合同授業グループを探す
            group_found = False
            for joint_group in resource.joint_sessions:
                if assignment.class_ref in joint_group:
                    # このグループの全メンバーを収集
                    group_members = []
                    for member_class in joint_group:
                        for a in assignments:
                            if a.class_ref == member_class:
                                group_members.append(a)
                                processed.add(member_class)
                    
                    if group_members:
                        groups.append(group_members)
                        group_found = True
                        break
            
            # 合同授業でない場合は単独グループ
            if not group_found:
                groups.append([assignment])
                processed.add(assignment.class_ref)
                
        return groups
        
    def check_assignment(self, context: ValidationContext) -> bool:
        """配置前チェック"""
        if not context.time_slot or not context.class_ref or not context.subject:
            return True
            
        # 該当するリソースを探す
        for resource_name, resource in self.resources.items():
            if context.subject in resource.subjects:
                # このリソースの現在の使用状況を確認
                current_usage = self._get_current_usage(context, resource)
                
                # 合同授業の一部かチェック
                is_joint = False
                for joint_group in resource.joint_sessions:
                    if context.class_ref in joint_group:
                        # 合同授業グループの他のメンバーが既に配置されているか
                        other_members_assigned = False
                        for member_class in joint_group:
                            if member_class != context.class_ref:
                                assignment = context.get_assignment_at(context.time_slot, member_class)
                                if assignment and assignment.subject and assignment.subject.name in resource.subjects:
                                    other_members_assigned = True
                                    break
                        
                        if other_members_assigned:
                            # 合同授業の一部として許可
                            is_joint = True
                            break
                
                # キャパシティチェック
                if not is_joint and len(current_usage) >= resource.capacity:
                    self.logger.debug(
                        f"{resource_name}は{context.time_slot}に既に{len(current_usage)}グループが使用中です"
                    )
                    return False
                    
        return True
        
    def _get_current_usage(self, context: ValidationContext, resource: Resource) -> List[Set[ClassReference]]:
        """現在のリソース使用グループを取得"""
        groups = []
        processed = set()
        
        assignments = context.get_assignments_by_time(context.time_slot)
        
        for assignment in assignments:
            if (assignment.subject and 
                assignment.subject.name in resource.subjects and
                assignment.class_ref not in processed):
                
                # 合同授業グループを探す
                group_found = False
                for joint_group in resource.joint_sessions:
                    if assignment.class_ref in joint_group:
                        # このグループのメンバーを収集
                        group_members = set()
                        for member_class in joint_group:
                            for a in assignments:
                                if (a.class_ref == member_class and 
                                    a.subject and 
                                    a.subject.name in resource.subjects):
                                    group_members.add(member_class)
                                    processed.add(member_class)
                        
                        if group_members:
                            groups.append(group_members)
                            group_found = True
                            break
                
                # 合同授業でない場合
                if not group_found:
                    groups.append({assignment.class_ref})
                    processed.add(assignment.class_ref)
                    
        return groups
        
    def get_available_resources(self, time_slot: TimeSlot, subject: str) -> List[str]:
        """指定時間・教科で利用可能なリソースを取得"""
        available = []
        
        for resource_name, resource in self.resources.items():
            if subject in resource.subjects:
                # 現在の使用状況を確認
                usage_count = 0
                for (res_name, ts), usages in self.resource_usage.items():
                    if res_name == resource_name and ts == time_slot:
                        usage_count = len(usages)
                        break
                
                if usage_count < resource.capacity:
                    available.append(resource_name)
                    
        return available
        
    def is_joint_session_valid(self, classes: Set[ClassReference], subject: str) -> bool:
        """指定されたクラスが合同授業として有効かチェック"""
        for resource_name, resource in self.resources.items():
            if subject in resource.subjects:
                for joint_group in resource.joint_sessions:
                    if classes.issubset(joint_group):
                        return True
                        
        return False