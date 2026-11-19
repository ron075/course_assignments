import html
import json
from pathlib import Path

import pytest
import pytest_html


ONLINE_CONFIG_PATH = Path(__file__).with_name("online_validation.json")


def pytest_addoption(parser):
    parser.addoption(
        "--run-online",
        action="store_true",
        default=False,
        help="run opt-in online analysis comparisons using saved inputs",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "online: compares application analysis with a documented public API",
    )
    config.addinivalue_line(
        "markers",
        "case(represents, category, expected): adds a readable test description",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-online"):
        return
    skip_online = pytest.mark.skip(
        reason="online API comparisons require explicit --run-online opt-in"
    )
    for item in items:
        if "online" in item.keywords:
            item.add_marker(skip_online)


@pytest.fixture
def case_report(request):
    comparisons = []
    request.node._case_comparisons = comparisons

    def record(
        *,
        represents,
        expected,
        actual,
        reference_name="Application reference",
        reference_url=None,
        raw_input=None,
    ):
        comparison = {
            "represents": represents,
            "expected": expected,
            "actual": actual,
            "reference_name": reference_name,
            "reference_url": reference_url,
        }
        if raw_input is not None and "online" not in request.node.keywords:
            comparison["raw_input"] = raw_input
        comparisons.append(comparison)

    return record


def _resolve_marker_value(value, parameters):
    if isinstance(value, str):
        for key, parameter in parameters.items():
            value = value.replace("{" + key + "}", repr(parameter))
    elif isinstance(value, dict):
        return {
            key: _resolve_marker_value(item, parameters)
            for key, item in value.items()
        }
    elif isinstance(value, list):
        return [_resolve_marker_value(item, parameters) for item in value]
    return value


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" and not (
        report.when == "setup" and report.outcome in {"failed", "skipped"}
    ):
        return

    marker = item.get_closest_marker("case")
    marker_data = {}
    if marker:
        for field in ("represents", "category", "expected"):
            value = marker.kwargs.get(field)
            if value is not None:
                if hasattr(item, "callspec"):
                    value = _resolve_marker_value(value, item.callspec.params)
                marker_data[field] = value

    comparisons = getattr(item, "_case_comparisons", [])
    if not comparisons and marker_data and report.outcome != "skipped":
        comparisons = [
            {
                "represents": marker_data.get("represents", item.name),
                "expected": marker_data.get("expected", "Test completes successfully"),
                "actual": f"Test outcome: {report.outcome}",
                "reference_name": "Application behavior",
            }
        ]

    properties = [
        ("test_group", "online" if "online" in item.keywords else "offline")
    ]
    if marker_data:
        properties.append(
            ("case_info", json.dumps(marker_data, ensure_ascii=False))
        )
    if comparisons:
        properties.append(
            ("case_comparisons", json.dumps(comparisons, ensure_ascii=False))
        )
    item.user_properties = properties
    report.user_properties = properties

    if not comparisons:
        return

    is_online = "online" in item.keywords
    identical_online_results = is_online and all(
        comparison.get("expected") == comparison.get("actual")
        for comparison in comparisons
    )
    rows = []
    for comparison in comparisons:
        reference_name = html.escape(comparison.get("reference_name", ""))
        url = comparison.get("reference_url")
        if isinstance(url, str) and url.startswith("https://"):
            reference_name = (
                f'<a href="{html.escape(url, quote=True)}">{reference_name}</a>'
            )
        checked = json.dumps(comparison.get("represents", ""), ensure_ascii=False)
        expected = json.dumps(
            comparison.get("expected", ""), ensure_ascii=False, indent=2
        )
        actual = json.dumps(
            comparison.get("actual", ""), ensure_ascii=False, indent=2
        )
        same = comparison.get("expected") == comparison.get("actual")
        if identical_online_results or (is_online and same):
            result_cell = (
                f"<td colspan='2'><pre>{html.escape(actual)}</pre></td>"
                if not identical_online_results
                else f"<td><pre>{html.escape(actual)}</pre></td>"
            )
            row = (
                f"<tr><td><pre>{html.escape(checked)}</pre></td>"
                f"{result_cell}<td>{reference_name}</td></tr>"
            )
            rows.append(row)
            continue
        columns = [checked, expected, actual, reference_name]
        rows.append(
            "<tr>"
            + "".join(
                f"<td><pre>{html.escape(str(value))}</pre></td>"
                if index < 3
                else f"<td>{value}</td>"
                for index, value in enumerate(columns)
            )
            + "</tr>"
        )
    if identical_online_results:
        headings = (
            "<th>What is checked</th><th>Validated result</th>"
            "<th>Reference API</th>"
        )
    else:
        headings = (
            "<th>What is checked</th><th>Online / expected</th>"
            "<th>Application result</th><th>Reference API</th>"
        )
    table = (
        f"<table class='case-comparison'><thead><tr>{headings}</tr></thead>"
        "<tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )
    extras = getattr(report, "extras", [])
    extras.append(pytest_html.extras.html(table))
    report.extras = extras


def load_online_config():
    if not ONLINE_CONFIG_PATH.is_file():
        pytest.skip(
            "No online input configuration exists; configure tests/online_validation.json."
        )
    try:
        config = json.loads(ONLINE_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        pytest.fail(f"Cannot read online test configuration: {exc}")
    if not isinstance(config, dict):
        pytest.fail("Online test configuration must be a JSON object.")
    if config.get("enabled") is not True:
        pytest.skip("Enable online comparisons in tests/online_validation.json.")
    return config
