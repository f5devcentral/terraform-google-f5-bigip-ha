"""Assertions for stateless module test cases."""

import re
from collections import Counter
from collections.abc import MutableSequence
from typing import Any

from google.cloud import compute_v1

from tests import (
    DEFAULT_INSTANCE_NAME_PATTERN,
    DEFAULT_TARGET_SIZE,
    AsserterFunc,
    Scenario,
    maximum_int_asserter_builder,
    re_asserter_builder,
)
from tests.template import DEFAULT_INSTANCE_TEMPLATE_SELF_LINK_PATTERN

DEFAULT_INSTANCE_GROUP_MANAGER_HEALTH_CHECK_SELF_LINK_PATTERN = re.compile(
    r"projects/([a-z][a-z0-9-]{4,28}[a-z0-9])/global/healthChecks/([a-z](?:[a-z0-9-]{0,61}[a-z0-9])?)$",
)
DEFAULT_INSTANCE_GROUP_MANAGER_DESCRIPTION_PATTERN = re.compile(
    r"^Managed group of regional stateless BIG-IP instances$",
)
DEFAULT_INSTANCE_GROUP_MANAGER_SELF_LINK_PATTERN = re.compile(
    r"projects/([a-z][a-z0-9-]{4,28}[a-z0-9])/regions/([a-z][a-z-]+[0-9])/instanceGroupManagers/([a-z](?:[a-z0-9-]{0,61}[a-z0-9])?)$",
)
DEFAULT_MANAGED_INSTANCE_EXPECTED_ACTION = "NONE"
DEFAULT_MANAGED_INSTANCE_EXPECTED_HEALTH_STATE = "HEALTHY"
DEFAULT_INSTANCE_GROUP_DESCRIPTION_PATTERN = re.compile(
    r"^This instance group is controlled by Regional Instance Group Manager '[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?'.",
)
DEFAULT_INSTANCE_GROUP_SELF_LINK_PATTERN = re.compile(
    r"projects/([a-z][a-z0-9-]{4,28}[a-z0-9])/regions/([a-z][a-z-]+[0-9])/instanceGroups/([a-z](?:[a-z0-9-]{0,61}[a-z0-9])?)$",
)


def default_assert_instance_group(
    instance_group: compute_v1.InstanceGroup | None,
    description_asserter: AsserterFunc | None = None,
    size_asserter: AsserterFunc | None = None,
) -> None:
    """Raise an AssertionError if the InstanceGroup object does not match expectations."""
    if description_asserter is None:
        description_asserter = re_asserter_builder(DEFAULT_INSTANCE_GROUP_DESCRIPTION_PATTERN)
    if size_asserter is None:
        size_asserter = maximum_int_asserter_builder(DEFAULT_TARGET_SIZE)
    assert instance_group is not None
    description_asserter(instance_group.description)
    size_asserter(instance_group.size)


def default_assert_instance_group_manager(
    manager: compute_v1.InstanceGroupManager | None,
    base_instance_name_asserter: AsserterFunc | None = None,
    description_asserter: AsserterFunc | None = None,
    instance_group_asserter: AsserterFunc | None = None,
    instance_template_asserter: AsserterFunc | None = None,
    expected_target_size: int | None = None,
) -> None:
    """Raise an AssertionError if the InstanceGroupManager object does not match expectations."""
    assert manager is not None
    if base_instance_name_asserter is None:
        base_instance_name_asserter = re_asserter_builder(DEFAULT_INSTANCE_NAME_PATTERN)
    if description_asserter is None:
        description_asserter = re_asserter_builder(DEFAULT_INSTANCE_GROUP_MANAGER_DESCRIPTION_PATTERN)
    if instance_group_asserter is None:
        instance_group_asserter = re_asserter_builder(DEFAULT_INSTANCE_GROUP_MANAGER_SELF_LINK_PATTERN)
    if instance_template_asserter is None:
        instance_template_asserter = re_asserter_builder(DEFAULT_INSTANCE_TEMPLATE_SELF_LINK_PATTERN)
    if expected_target_size is None:
        expected_target_size = DEFAULT_TARGET_SIZE
    base_instance_name_asserter(manager.base_instance_name)
    description_asserter(manager.description)
    instance_group_asserter(manager.instance_group)
    instance_template_asserter(manager.instance_template)
    assert manager.target_pools is not None
    assert manager.target_pools == []
    assert manager.target_size == expected_target_size
    assert manager.target_stopped_size == 0
    assert manager.target_suspended_size == 0


def default_assert_instance_group_manager_all_instances_config(
    config: compute_v1.InstanceGroupManagerAllInstancesConfig | None,
) -> None:
    """Raise an AssertionError if the InstanceGroupManagerAllInstancesConfig object does not match expectations."""
    assert config is not None
    assert config.properties is not None
    assert config.properties.labels is not None
    assert config.properties.labels == {}
    assert config.properties.metadata is not None
    assert config.properties.metadata == {}


def default_assert_instance_group_manager_auto_healing_policies(
    policies: MutableSequence[compute_v1.InstanceGroupManagerAutoHealingPolicy] | None,
    health_check_asserter: AsserterFunc | None = None,
) -> None:
    """Raise an AssertionError if the any of InstanceGroupManagerAutoHealingPolicy objects don't meet expectations."""
    if health_check_asserter is None:
        health_check_asserter = re_asserter_builder(DEFAULT_INSTANCE_GROUP_MANAGER_HEALTH_CHECK_SELF_LINK_PATTERN)
    assert policies is not None
    assert len(policies) == 1
    for policy in policies:
        assert policy is not None
        health_check_asserter(policy.health_check)
        assert policy.initial_delay_sec == 600  # noqa: PLR2004


def default_assert_instance_group_manager_actions_summary(
    summary: compute_v1.InstanceGroupManagerActionsSummary | None,
) -> None:
    """Raise an AssertionError if the InstanceGroupManagerActionsSummary object does not match expectations.

    NOTE: This function only checks the values for statuses that should never be triggered by the module.
    """
    assert summary is not None
    assert not summary.abandoning
    assert not summary.resuming
    assert not summary.suspending


def default_assert_distribution_policy(
    policy: compute_v1.DistributionPolicy | None,
    expected_zones: list[str] | None = None,
) -> None:
    """Raise an AssertionError if the DistributionPolicy object does not meet expectations."""
    assert policy is not None
    assert policy.target_shape == "EVEN"
    if expected_zones is not None:
        # If expected zones are given, only those zones should be part of the policy
        policy_zones = [entry.zone for entry in policy.zones]
        assert Counter(policy_zones) == Counter(expected_zones)
    else:
        # Expect any deployment to be distributed over multiple zones
        assert len(policy.zones) > 1


def default_assert_instance_group_manager_instance_flexibility_policy(
    policy: compute_v1.InstanceGroupManagerInstanceFlexibilityPolicy | None,
) -> None:
    """Raise an AssertionError if InstanceGroupManagerInstanceFlexibilityPolicy object does not meet expectations."""
    assert policy is not None
    assert policy.instance_selections is not None
    assert policy.instance_selections == {}


def default_assert_instance_group_manager_instance_lifecycle_policy(
    policy: compute_v1.InstanceGroupManagerInstanceLifecyclePolicy | None,
) -> None:
    """Raise an AssertionError if the InstanceGroupManagerInstanceLifecyclePolicy object does not meet expectations."""
    assert policy is not None
    assert policy.default_action_on_failure == "REPAIR"
    assert policy.force_update_on_repair == "YES"


def default_assert_named_ports(
    named_ports: MutableSequence[compute_v1.NamedPort] | None,
    expected_named_ports: dict[str, int] | None = None,
) -> None:
    """Raise an AssertionError if the sequence of NamedPort objects does not match expectations."""
    assert named_ports is not None
    if expected_named_ports is not None:
        actual_named_ports = {entry.name: entry.port for entry in named_ports}
        assert all(item in actual_named_ports.items() for item in expected_named_ports.items())
    else:
        assert len(named_ports) == 0


def default_assert_instance_group_manager_resource_policies(
    policies: compute_v1.InstanceGroupManagerResourcePolicies | None,
) -> None:
    """Raise an AssertionError if the InstanceGroupManagerResourcePolicies objects does not match expectations."""
    assert policies is not None
    assert not policies.workload_policy


def default_assert_instance_group_manager_standby_policy(
    policy: compute_v1.InstanceGroupManagerStandbyPolicy | None,
) -> None:
    """Raise an AssertionError if the InstanceGroupManagerStandbyPolicy object does not match expectations."""
    assert policy is not None
    assert not policy.initial_delay_sec
    assert policy.mode == "MANUAL"


def default_assert_stateful_policy(policy: compute_v1.StatefulPolicy | None) -> None:
    """Raise an AssertionError if the StatefulPolicy object does not match expectations."""
    assert policy is not None
    assert not policy.preserved_state


def default_assert_instance_group_manager_status(status: compute_v1.InstanceGroupManagerStatus | None) -> None:
    """Raise an AssertionError if the InstanceGroupManagerStatus object does no match expectations.

    NOTE: The MIG could be actively changing instances so only predictable fields are verified.
    """
    assert status is not None
    assert status.all_instances_config is not None
    assert status.all_instances_config.effective
    assert not status.autoscaler
    assert status.stateful is not None
    assert not status.stateful.has_stateful_config
    assert status.stateful.per_instance_configs is not None
    assert status.stateful.per_instance_configs.all_effective
    assert status.version_target is not None
    assert status.version_target.is_reached


def default_assert_instance_group_manager_update_policy(
    policy: compute_v1.InstanceGroupManagerUpdatePolicy | None,
    expected_max_surge: int | None = None,
) -> None:
    """Raise an AssertionError if the InstanceGroupManagerUpdatePolicy object does not match expectations."""
    assert policy is not None
    assert policy.instance_redistribution_type == "NONE"
    assert policy.max_surge is not None
    if expected_max_surge is None:
        assert policy.max_surge.fixed > 0
    else:
        assert policy.max_surge.fixed == expected_max_surge
    assert not policy.max_surge.percent
    assert policy.max_unavailable is not None
    assert policy.max_unavailable.fixed == 0
    assert not policy.max_unavailable.percent
    assert policy.minimal_action == "REPLACE"
    assert policy.most_disruptive_allowed_action == "REPLACE"
    assert policy.replacement_method == "SUBSTITUTE"
    assert policy.type_ == "OPPORTUNISTIC"


def default_assert_instance_group_manager_versions(
    versions: MutableSequence[compute_v1.InstanceGroupManagerVersion] | None,
    instance_template_asserter: AsserterFunc | None = None,
) -> None:
    """Raise an AssertionError if the sequence of InstanceGroupManagerVersion objects does not meet expectations."""
    if instance_template_asserter is None:
        instance_template_asserter = re_asserter_builder(DEFAULT_INSTANCE_TEMPLATE_SELF_LINK_PATTERN)
    assert versions is not None
    assert len(versions) == 1
    for version in versions:
        assert version
        instance_template_asserter(version.instance_template)
        assert not version.name
        assert version.target_size is not None
        assert not version.target_size.fixed
        assert not version.target_size.percent


def default_assert_managed_instance(
    instance: compute_v1.ManagedInstance | None,
    expected_actions: list[str] | None = None,
) -> None:
    """Raise an AssertionError if the ManagedInstance object does not meet expectations."""
    if expected_actions is None:
        expected_actions = [DEFAULT_MANAGED_INSTANCE_EXPECTED_ACTION]
    assert instance is not None
    assert instance.current_action in expected_actions


def default_assert_managed_instance_instance_health(
    values: MutableSequence[compute_v1.ManagedInstanceInstanceHealth] | None,
    expected_states: list[str] | None = None,
) -> None:
    """Raise an AssertionError if the sequence of ManagedInstanceInstanceHealth objects do not meet expectations."""
    if expected_states is None:
        expected_states = [DEFAULT_MANAGED_INSTANCE_EXPECTED_HEALTH_STATE]
    assert values is not None
    assert len(values) == 1
    for health in values:
        assert health.detailed_health_state in expected_states
        assert health.health_check


class StatelessScenario(Scenario):
    """Encapsulates a stateless single BIG-IP version + NIC count template and MIG test scenario."""

    def __init__(
        self,
        bigip_key: str,
        nic_count: int,
        prefix: str | None = None,
    ) -> None:
        """Initialize a StatefulScenario."""
        super().__init__(bigip_key, nic_count, prefix)
        self._stateless_tfvars: dict[str, Any] = {}

    @property
    def stateless_tfvars(self) -> dict[str, Any]:
        """Return the stateless tfvars for scenario."""
        return self._stateless_tfvars | {
            "prefix": self.__str__(),
        }

    @stateless_tfvars.setter
    def stateless_tfvars(self, value: dict[str, Any]) -> None:
        """Replace stateless tfvars with given value."""
        self._stateless_tfvars = value
