from backend.app.services import objective_specs
from workers.agent.execution import MetaDraftBuildRuntime
from workers.agent.meta_fields import action_blocks, build_stage_plan, read_spec_value


def adapter(objective: str) -> dict:
    spec = objective_specs.get_spec(objective)
    assert spec is not None
    return spec.as_payload()


def test_sales_ad_plan_contains_exact_identity_url_and_creative_actions():
    spec = {
        "targeting": {
            "page_name": "Lush Media",
            "dataset_name": "Lush Pixel",
            "conversion_event": "Purchase",
        },
        "creative": {
            "asset_local_path": "C:/tmp/creative.png",
            "primary_text": "Nội dung kiểm thử",
            "headline": "Tiêu đề kiểm thử",
            "destination_url": "https://example.com/landing",
            "cta": "SHOP_NOW",
        },
    }
    plan = build_stage_plan(adapter("sales"), spec, "ad")
    assert [item.handler for item in plan] == [
        "page_exact",
        "media_upload",
        "destination_url",
        "primary_text",
        "headline",
        "cta",
        "dataset",
        "conversion_event",
    ]
    assert all(item.value for item in plan)
    assert next(item for item in plan if item.handler == "media_upload").required is True
    assert next(item for item in plan if item.handler == "destination_url").required is True
    assert next(item for item in plan if item.handler == "dataset").required is False


def test_awareness_plan_never_invents_destination_url():
    spec = {
        "targeting": {"page_name": "Lush Media", "countries": ["VN"]},
        "creative": {
            "asset_local_path": "C:/tmp/creative.png",
            "primary_text": "Nhận biết thương hiệu",
        },
    }
    adset = build_stage_plan(adapter("awareness"), spec, "adset")
    ad = build_stage_plan(adapter("awareness"), spec, "ad")
    assert [item.handler for item in adset] == [
        "page_exact",
        "countries_exact",
        "age_min",
        "age_max",
        "placements",
    ]
    assert "media_upload" in {item.handler for item in ad}
    assert "destination_url" not in {item.handler for item in ad}


def test_app_and_lead_actions_stay_on_their_surveyed_stages():
    app_spec = {
        "targeting": {
            "countries": ["VN"],
            "app_name": "Lush App",
            "app_store_country": "VN",
        },
        "creative": {},
    }
    app_adset = build_stage_plan(adapter("app_promotion"), app_spec, "adset")
    assert [item.handler for item in app_adset][-2:] == ["app_name", "app_store_country"]

    lead_spec = {
        "targeting": {"page_name": "Lush Media"},
        "creative": {"lead_form_name": "Lead Form 01"},
    }
    lead_ad = build_stage_plan(adapter("leads"), lead_spec, "ad")
    assert next(item for item in lead_ad if item.handler == "lead_form").value == "Lead Form 01"


def test_missing_required_value_blocks_only_at_terminal_action():
    plan = build_stage_plan(
        adapter("traffic"),
        {"targeting": {}, "creative": {}},
        "ad",
    )
    destination = next(item for item in plan if item.handler == "destination_url")
    result = destination.as_result("blocked", "Thiếu giá trị trong approved snapshot.")
    assert destination.value == ""
    assert action_blocks(result) is True


def test_read_spec_value_normalizes_lists_for_future_targeting_handlers():
    assert read_spec_value({"targeting": {"countries": ["VN", "TH"]}}, "targeting.countries") == "VN,TH"


def test_country_handler_recognizes_lazy_rendered_existing_value(monkeypatch):
    bodies = iter(("Tên nhóm quảng cáo", "Kiểm soát đối tượng", "Bao gồm vị trí: Việt Nam"))

    monkeypatch.setattr(
        MetaDraftBuildRuntime,
        "_body",
        classmethod(lambda cls, socket, command_id: (command_id + 1, next(bodies))),
    )
    monkeypatch.setattr(
        MetaDraftBuildRuntime,
        "_rewind_editor",
        classmethod(lambda cls, socket, command_id: command_id + 1),
    )
    monkeypatch.setattr(
        MetaDraftBuildRuntime,
        "_scroll_editor_down",
        classmethod(lambda cls, socket, command_id: (command_id + 1, True)),
    )
    monkeypatch.setattr("workers.agent.execution.time.sleep", lambda _seconds: None)

    _command_id, status = MetaDraftBuildRuntime._apply_countries_exact(None, 1, "VN")

    assert status == "already_set"


def test_page_handler_uses_selected_control_instead_of_helper_copy(monkeypatch):
    expressions: list[str] = []

    def evaluate(_cls, _socket, _command_id, expression):
        expressions.append(expression)
        return True

    monkeypatch.setattr(
        MetaDraftBuildRuntime,
        "_evaluate",
        classmethod(evaluate),
    )
    monkeypatch.setattr(
        MetaDraftBuildRuntime,
        "_rewind_editor",
        classmethod(lambda cls, socket, command_id: command_id + 1),
    )
    monkeypatch.setattr("workers.agent.execution.time.sleep", lambda _seconds: None)

    _command_id, status = MetaDraftBuildRuntime._apply_page_exact(
        None,
        1,
        "Stable Diffusion AI",
        "113903128387475",
        5,
    )

    assert status == "already_set"
    assert "[role=\"combobox\"]" in expressions[0]
    assert "Stable Diffusion AI" in expressions[0]
