from unittest.mock import MagicMock

import ops
import pytest
import scenario

from litmus_libs.status_manager import StatusManager


@pytest.mark.parametrize(
    "spec, expected_missing",
    (
        ({"foo": None, "bar": None, "baz": None}, "foo, bar, baz"),
        ({"foo": None, "bar": None, "baz": 42}, "foo, bar"),
        ({"foo": True, "bar": None, "baz": 42}, "bar"),
        ({"foo": True, "bar": [42], "baz": 42}, ""),
    )

)
def test_manager_sets_waiting_on_config_missing(spec, expected_missing):
    sm = StatusManager(MagicMock(), wait_for_config=spec)
    event = MagicMock()
    sm.collect_status(event)
    if not expected_missing:
        assert not event.add_status.called
    else:
        assert event.add_status.called
        call_args = event.add_status.call_args
        expected_msg = sm._configs_missing_msg_template.format(expected_missing)
        assert call_args.args[0].message == expected_msg


@pytest.mark.parametrize(
    "required, present, expected_missing",
    (
        (["foo", "bar"], ["foo"], "bar"),
        (["foo", "bar", "baz"], ["foo"], "bar, baz"),
        (["foo", "bar", "baz"], ["foo", "bar", "baz"], ""),
    )

)
def test_manager_sets_waiting_on_relations_missing(required, present, expected_missing):
    charm = MagicMock()
    charm.model.get_relation = lambda name: name in present
    sm = StatusManager(charm, block_if_relations_missing=required)
    event = MagicMock()
    sm.collect_status(event)
    if not expected_missing:
        assert not event.add_status.called
    else:
        assert event.add_status.called
        call_args = event.add_status.call_args
        expected_msg = sm._relations_missing_msg_template.format(expected_missing)
        assert call_args.args[0].message == expected_msg



@pytest.mark.parametrize(
    "required, passing, expected_failing",
    (
        (["foo", "bar"], ["foo"], "bar"),
        (["foo", "bar", "baz"], ["foo"], "bar, baz"),
        (["foo", "bar", "baz"], ["foo", "bar", "baz"], ""),
    )

)
def test_manager_sets_blocked_on_checks_failing(required, passing, expected_failing):
    charm = MagicMock()
    check_status = {name: ops.pebble.CheckInfo(name,
                                               level=ops.pebble.CheckLevel.READY,
                                               status=(ops.pebble.CheckStatus.UP if name in passing else ops.pebble.CheckStatus.DOWN))
                    for name in required}
    charm.unit.get_container.return_value.get_checks = lambda *_: check_status
    sm = StatusManager(charm, block_if_pebble_checks_failing={"container": required})
    event = MagicMock()
    sm.collect_status(event)
    if not expected_failing:
        assert not event.add_status.called
    else:
        assert event.add_status.called
        call_args = event.add_status.call_args
        expected_msg = sm._checks_failing_msg_template.format(expected_failing)
        assert call_args.args[0].message == expected_msg



@pytest.fixture
def ctx():
    class MyCharm(ops.CharmBase):
        META = {"name": "bartlomiej",
                "containers": {"container1": {}},
                "requires": {"rel1": {"interface": "bar"}},
                }
        CONFIG={"options":{"cfg1": {"type": "boolean"}}}

        def __init__(self, f):
            super().__init__(f)
            self.framework.observe(self.on.collect_unit_status, self._collect_status)

        def _collect_status(self, e):
            StatusManager(self,
                          wait_for_config={"cfg1": self.config.get('cfg1'), "bar": 1, "baz": 0},
                          block_if_pebble_checks_failing={"container1": ("check1", )},
                          block_if_relations_missing=['rel1']
                          ).collect_status(e)
            e.add_status(ops.ActiveStatus("happy status!"))

    ctx = scenario.Context(MyCharm, meta=MyCharm.META, config=MyCharm.CONFIG)
    return ctx


@pytest.mark.parametrize("fail", ("checks", "relation", "config", None))
def test_status_mgr_charm_api_checks(ctx, fail):
    check_status = ops.pebble.CheckStatus.DOWN if fail == "checks" else ops.pebble.CheckStatus.UP

    state_in = scenario.State(
        config={} if fail =="config" else {"cfg1": True},
        relations= {} if fail == "relation" else {scenario.Relation("rel1")},
        containers={
            scenario.Container("container1",
                               _base_plan={"checks": {"check1":{"threshold": 3,
                                                                "startup": "enabled",
                                                                "level": None}}},
                               check_infos={scenario.CheckInfo("check1", status=check_status)})
        }
    )
    state_out = ctx.run(ctx.on.update_status(), state=state_in)

    match fail:
        case "checks":
            assert state_out.unit_status.message == StatusManager._checks_failing_msg_template.format("check1")
        case "relation":
            assert state_out.unit_status.message == StatusManager._relations_missing_msg_template.format("rel1")
        case "config":
            assert state_out.unit_status.message == StatusManager._configs_missing_msg_template.format("cfg1")
        case None:
            assert state_out.unit_status.message == "happy status!"

