from backend.app.services import objective_specs
from workers.agent.execution import MetaDraftBuildRuntime


def test_all_six_objectives_have_surveyed_default_path():
    specs = objective_specs.list_specs()
    assert [item["key"] for item in specs] == [
        "awareness",
        "traffic",
        "engagement",
        "leads",
        "app_promotion",
        "sales",
    ]
    assert all(item["automation_level"] == "field_filling" for item in specs)
    traffic = next(item for item in specs if item["key"] == "traffic")
    assert traffic["setup_mode"] == "manual"
    assert traffic["manual_setup_label"] == "Chiến dịch lưu lượng truy cập thủ công"
    assert traffic["default_conversion_location"] == "website"
    assert any(
        action["handler"] == "destination_url" and action["stage"] == "ad"
        for action in traffic["field_actions"]
    )


def test_objective_warnings_are_specific_instead_of_universal_destination_url():
    awareness_blockers, awareness_warnings = objective_specs.build_spec_warnings(
        "awareness",
        {"countries": ["VN"]},
        {},
    )
    assert awareness_blockers == []
    assert any("Page Facebook" in item for item in awareness_warnings)
    assert any("primary text" in item for item in awareness_warnings)
    assert not any("destination URL" in item for item in awareness_warnings)

    sales_blockers, sales_warnings = objective_specs.build_spec_warnings(
        "sales",
        {"countries": ["VN"], "conversion_location": "website"},
        {},
    )
    assert sales_blockers == []
    assert any("destination URL" in item for item in sales_warnings)
    assert any("Pixel/dataset" in item for item in sales_warnings)


def test_non_default_conversion_location_is_blocked_until_adapter_exists():
    blockers, _warnings = objective_specs.build_spec_warnings(
        "traffic",
        {"conversion_location": "messaging_apps", "countries": ["VN"]},
        {},
    )
    assert blockers
    assert "default path" in blockers[0]


def test_worker_legacy_contract_keeps_traffic_manual_setup():
    adapter = MetaDraftBuildRuntime.LEGACY_ADAPTERS["traffic"]
    assert adapter["setup_mode"] == "manual"
    assert "creative.destination_url" in adapter["required_fields"]
    assert any(
        action["handler"] == "destination_url"
        for action in MetaDraftBuildRuntime.LEGACY_FIELD_ACTIONS["traffic"]
    )
