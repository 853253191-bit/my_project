# -*- coding: utf-8 -*-
"""Pydantic Schema 测试（SPEC 附录 A）。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from manus.schemas.models import (
    ApprovalHints,
    BottleneckItem,
    ChecklistGateResult,
    ComponentNode,
    NewsItem,
    RedTeamReport,
    RunDetail,
    StepApprovalView,
    StepResolveRequest,
    SupplierProfile,
    ValidationReport,
)
from tests.helpers.builders import make_checklist_gate, make_supplier


class TestNewsItem:
    def test_round_trip(self, sample_news_item):
        item = NewsItem.model_validate(sample_news_item)
        dumped = item.model_dump(mode="json")
        assert dumped["hardware_focus"] is True
        assert NewsItem.model_validate(dumped).id == sample_news_item["id"]

    def test_max_five_not_enforced_at_model_level(self, sample_news_item):
        # 列表长度由 Agent1 业务逻辑约束，模型本身可解析单条
        NewsItem.model_validate(sample_news_item)


class TestSupplierProfile:
    def test_main_board_valid(self, sample_supplier_main):
        sp = SupplierProfile.model_validate(sample_supplier_main)
        assert sp.market == "CN"
        assert sp.listing_board == "main"
        assert sp.is_st is False

    def test_st_flag_rejected(self):
        data = make_supplier(is_st=True)
        with pytest.raises(ValidationError):
            SupplierProfile.model_validate(data)

    def test_non_main_board_rejected(self):
        data = make_supplier(listing_board="star")
        with pytest.raises(ValidationError):
            SupplierProfile.model_validate(data)


class TestBottleneckItem:
    def test_traits_enum(self):
        item = BottleneckItem.model_validate(
            {
                "id": "bn-1",
                "component": "光引擎",
                "bottleneck_name": "InP",
                "layer": "material",
                "traits": {
                    "mandatory": "true",
                    "oligopoly": "unknown",
                    "slow_expansion": "false",
                    "low_coverage": "true",
                },
                "mismatch_hypothesis": "供需错配",
                "evidence": ["年报"],
            }
        )
        assert item.traits.mandatory == "true"


class TestValidationReport:
    def test_irreplaceability_range(self):
        with pytest.raises(ValidationError):
            ValidationReport.model_validate(
                {
                    "bottleneck_id": "bn-1",
                    "irreplaceability_score": 6,
                    "supply_test": {
                        "architecture_change_required": True,
                        "switching_time_months": 12,
                        "hoarding_signals": "有",
                        "switching_cost": "high",
                    },
                    "assumptions": ["假设1"],
                    "checklist_pass": [],
                }
            )


class TestRedTeamReport:
    def test_min_falsification_items(self):
        with pytest.raises(ValidationError):
            RedTeamReport.model_validate(
                {
                    "alternative_routes": ["路线A"],
                    "falsification_data_needed": ["d1", "d2"],
                    "supply_response_risk": "扩产超预期",
                    "needs_human_review": True,
                }
            )


class TestChecklistGateResult:
    def test_hard_fail(self):
        gate = ChecklistGateResult.model_validate(make_checklist_gate(hard_fail=True))
        assert gate.result == "hard_fail"
        assert "H3_supply_test" in gate.failed_hard_ids


class TestApprovalHints:
    def test_block_proceed(self):
        hints = ApprovalHints(block_proceed=True, outlook_stop=True, messages=["终端需求停止"])
        assert hints.block_proceed is True


class TestStepResolveRequest:
    @pytest.mark.parametrize("action", ["proceed", "rerun", "change_direction"])
    def test_valid_actions(self, action: str):
        req = StepResolveRequest(action=action)
        assert req.action == action

    def test_step0_proceed_with_news_id(self):
        req = StepResolveRequest(action="proceed", news_id="news-001")
        assert req.news_id == "news-001"


class TestRunDetail:
    def test_status_enum(self, filled_pipeline_state_dict):
        detail = RunDetail.model_validate(
            {
                "run_id": filled_pipeline_state_dict["run_id"],
                "run_date": filled_pipeline_state_dict["run_date"],
                "status": "awaiting_step_approval",
                "pending_approval_step": 0,
            }
        )
        assert detail.status == "awaiting_step_approval"


class TestStepApprovalView:
    def test_step_output_mapping_step0(self, sample_news_item):
        view = StepApprovalView(
            run_id="run-1",
            step=0,
            agent=1,
            agent_name="NewsCollector",
            status="awaiting_step_approval",
            step_output_summary="Top5 采集完成",
            approval_hints=ApprovalHints(),
            output={"news_items": [sample_news_item]},
        )
        assert view.step == 0
        assert view.agent == 1


class TestComponentNode:
    def test_horizontal_branches(self, filled_pipeline_state_dict):
        node = ComponentNode.model_validate(filled_pipeline_state_dict["component_node"])
        assert node.decomposition_depth >= 1
        assert len(node.horizontal_branches) >= 1
