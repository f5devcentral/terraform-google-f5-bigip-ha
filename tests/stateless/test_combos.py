"""Test fixture for stateless BIG-IP HA deployment with multiple versions and NIC counts.

This test case will create stateless BIG-IP HA deployments using the root module for each BIG-IP version known to this
test package and NICs for [1, MAX_NIC_COUNT]. See the constants in tests/__init__.py for current values.

NOTE: Public IP addresses will be added to the first and second interface so that the state of the BIG-IP VE can be
      validated, and Guest Attributes are enabled through instance metadata so that the test cases can wait for
      onboarding to complete.
"""

import ipaddress
import pathlib
import re
from collections.abc import Callable, Generator
from typing import Any, cast

import pytest
from google.cloud import compute_v1

from tests import (
    DEFAULT_TARGET_SIZE,
    MAX_NIC_COUNT,
    default_assert_accelerator_configs,
    default_assert_advanced_machine_features,
    default_assert_confidential_instance_config,
    default_assert_customer_encryption_key,
    default_assert_disks,
    default_assert_display_device,
    default_assert_instance,
    default_assert_labels,
    default_assert_metadata,
    default_assert_network_interfaces,
    default_assert_network_performance_config,
    default_assert_reservation_affinity,
    default_assert_resource_policies,
    default_assert_resource_status,
    default_assert_scheduling,
    default_assert_service_accounts,
    default_assert_shielded_instance_config,
    default_assert_shielded_instance_integrity_policy,
    default_assert_tags,
    equal_asserter_builder,
    re_asserter_builder,
    run_tf_in_workspace,
    scenario_generator,
    scenario_id_builder,
    unset_asserter,
)
from tests.stateless import (
    DEFAULT_INSTANCE_GROUP_MANAGER_SELF_LINK_PATTERN,
    DEFAULT_INSTANCE_GROUP_SELF_LINK_PATTERN,
    StatelessScenario,
    default_assert_distribution_policy,
    default_assert_instance_group,
    default_assert_instance_group_manager,
    default_assert_instance_group_manager_actions_summary,
    default_assert_instance_group_manager_all_instances_config,
    default_assert_instance_group_manager_auto_healing_policies,
    default_assert_instance_group_manager_instance_flexibility_policy,
    default_assert_instance_group_manager_instance_lifecycle_policy,
    default_assert_instance_group_manager_resource_policies,
    default_assert_instance_group_manager_standby_policy,
    default_assert_instance_group_manager_status,
    default_assert_instance_group_manager_update_policy,
    default_assert_instance_group_manager_versions,
    default_assert_managed_instance,
    default_assert_managed_instance_instance_health,
    default_assert_named_ports,
    default_assert_stateful_policy,
)

FIXTURE_NAME = "sles-combo"


@pytest.fixture(scope="module")
def fixture_name(prefix: str) -> str:
    """Return the name to use for resources in this module."""
    return f"{prefix}-{FIXTURE_NAME}"


@pytest.fixture(scope="module")
def fixture_labels(fixture_name: str, labels: dict[str, str]) -> dict[str, str]:
    """Return a dict of labels for this test module."""
    return {"fixture": fixture_name} | labels


@pytest.fixture(scope="module")
def sa_email(service_account_builder: Callable[..., str], fixture_name: str) -> str:
    """Create a service account for this test case and return it's email identifier."""
    return service_account_builder(name=fixture_name, display_name="Minimal BIG-IP stateless HA")


@pytest.fixture(scope="module")
def fixture_metadata() -> dict[str, str]:
    """Return a metadata dictionary with block-project-ssh-keys enabled, an instance SSH key, and minimal user-data."""
    return {
        "block-project-ssh-keys": "TRUE",
        "enable-guest-attributes": "TRUE",
    }


@pytest.fixture(scope="module")
def subnet_ranges(
    subnet_ranges_builder: Callable[[int | None], list[ipaddress.IPv4Network]],
) -> list[ipaddress.IPv4Network]:
    """Return a list of subnet CIDRs for this test case."""
    return subnet_ranges_builder(MAX_NIC_COUNT)


@pytest.fixture(scope="module")
def subnet_self_links(
    fixture_name: str,
    subnet_ranges: list[ipaddress.IPv4Network],
    network_builder: Callable[..., str],
    subnet_builder: Callable[..., str],
    allow_ingress_firewall_builder: Callable[..., str],
) -> list[str]:
    """Create testing VPC subnets for external and management interfaces, returning their self-links."""
    subnets: list[str] = []
    for i, cidr in enumerate(subnet_ranges):
        vpc_name = f"{fixture_name}-{i}"
        network_self_link = network_builder(name=vpc_name)
        if min(len(subnet_ranges) - 1, 1):
            allow_ingress_firewall_builder(network=network_self_link, name=vpc_name)
        subnets.append(subnet_builder(name=vpc_name, cidr=str(cidr), network_self_link=network_self_link))
    return subnets


@pytest.fixture(scope="module")
def common_template_tfvars(
    project_id: str,
    fixture_labels: dict[str, str],
    fixture_metadata: dict[str, str],
    runtime_init_conf: str,
    sa_email: str,
) -> dict[str, Any]:
    """Return a dict of tfvars common to all tests in this module."""
    return {
        "project_id": project_id,
        "service_account": sa_email,
        "labels": fixture_labels,
        "metadata": fixture_metadata,
        "runtime_init_config": runtime_init_conf,
        "runtime_init_installer": {
            "skip_telemetry": True,
        },
    }


@pytest.fixture(scope="module")
def common_stateless_tfvars(
    project_id: str,
) -> dict[str, Any]:
    """Return a dict of tfvars common to all tests in this module."""
    return {
        "project_id": project_id,
    }


@pytest.fixture(
    scope="module",
    params=scenario_generator(StatelessScenario, minimum_nic_count=1),
    ids=scenario_id_builder,
)
def scenario(
    request: pytest.FixtureRequest,
    fixture_name: str,
    common_template_tfvars: dict[str, Any],
    common_stateless_tfvars: dict[str, Any],
    subnet_self_links: list[str],
    runtime_init_conf_1nic: str,
) -> StatelessScenario:
    """Return a Scenario objects for the combination of BIG-IP images under test and NIC counts."""
    scenario = cast("StatelessScenario", request.param)
    scenario.prefix = fixture_name
    template_tfvars = common_template_tfvars | {
        "interfaces": [
            {
                "subnet_id": self_link,
                "public_ip": i == min(scenario.nic_count - 1, 1),
            }
            for i, self_link in enumerate(subnet_self_links)
            if i < scenario.nic_count
        ],
    }
    # Single-NIC scenario must use the runtime-init configuration that is specific to it
    if scenario.nic_count == 1:
        template_tfvars["runtime_init_config"] = runtime_init_conf_1nic
    scenario.tfvars = template_tfvars
    scenario.stateless_tfvars = common_stateless_tfvars
    return scenario


@pytest.fixture(scope="module")
def template_fixture_output(
    template_fixture_dir: Callable[[str], pathlib.Path],
    scenario: StatelessScenario,
) -> Generator[tuple[StatelessScenario, dict[str, Any]]]:
    """Create an Instance Template for test scenario."""
    with run_tf_in_workspace(
        fixture=template_fixture_dir(f"{scenario!s}-tmpl"),
        tfvars=scenario.tfvars,
    ) as output:
        self_link = cast("str", output["self_link"])
        assert self_link
        scenario.stateless_tfvars = scenario.stateless_tfvars | {"instance_template": self_link}
        yield (scenario, output)


@pytest.fixture(scope="module")
def fixture_output(
    fixture_dir: Callable[[str], pathlib.Path],
    template_fixture_output: tuple[StatelessScenario, dict[str, Any]],
    wait_for_instance_group_manager_deleted: Callable[..., None],
) -> Generator[tuple[StatelessScenario, dict[str, Any]]]:
    """Create a MIG using template for test scenario."""
    scenario = template_fixture_output[0]
    with run_tf_in_workspace(
        fixture=fixture_dir(str(scenario)),
        tfvars=scenario.stateless_tfvars,
    ) as output:
        self_link = cast("str", output["instance_group_manager"])
        yield (scenario, output)
    wait_for_instance_group_manager_deleted(self_link)


@pytest.fixture(scope="module")
def managed_instances_for_scenario(
    region_instance_group_managers_client: compute_v1.RegionInstanceGroupManagersClient,
    fixture_output: tuple[StatelessScenario, dict[str, Any]],
) -> tuple[StatelessScenario, list[compute_v1.ManagedInstance]]:
    """Return the list of Compute Engine ManagedInstances."""
    scenario = fixture_output[0]
    output_values = fixture_output[1]
    self_link = cast("str", output_values["instance_group_manager"])
    assert self_link
    match = re.search(DEFAULT_INSTANCE_GROUP_MANAGER_SELF_LINK_PATTERN, self_link)
    assert match
    project, region, name = match.groups()
    return (
        scenario,
        list(
            region_instance_group_managers_client.list_managed_instances(
                request=compute_v1.ListManagedInstancesRegionInstanceGroupManagersRequest(
                    project=project,
                    region=region,
                    instance_group_manager=name,
                ),
            ),
        ),
    )


@pytest.fixture(scope="module")
def instances_for_scenario(
    instances_builder: Callable[[list[str]], list[compute_v1.Instance]],
    wait_for_onboarding_complete: Callable[..., compute_v1.Instance],
    managed_instances_for_scenario: tuple[StatelessScenario, list[compute_v1.ManagedInstance]],
) -> tuple[StatelessScenario, list[compute_v1.Instance]]:
    """Return a list of Compute Engine Instances from ManagedInstances list."""
    scenario = managed_instances_for_scenario[0]
    managed_instances = managed_instances_for_scenario[1]
    return (
        scenario,
        [
            wait_for_onboarding_complete(instance)
            for instance in instances_builder([managed_instance.instance for managed_instance in managed_instances])
        ],
    )


@pytest.fixture(scope="module")
def instance_group_manager_for_scenario(
    region_instance_group_managers_client: compute_v1.RegionInstanceGroupManagersClient,
    fixture_output: tuple[StatelessScenario, dict[str, Any]],
    instances_for_scenario: tuple[StatelessScenario, list[compute_v1.Instance]],  # noqa: ARG001 # Depend on BIG-IP VE onboarding to complete
) -> tuple[StatelessScenario, compute_v1.InstanceGroupManager]:
    """Return an InstanceGroupManager from the output."""
    scenario = fixture_output[0]
    output_values = fixture_output[1]
    self_link = cast("str", output_values["instance_group_manager"])
    assert self_link
    match = re.search(DEFAULT_INSTANCE_GROUP_MANAGER_SELF_LINK_PATTERN, self_link)
    assert match
    project, region, name = match.groups()
    mig = region_instance_group_managers_client.get(
        request=compute_v1.GetRegionInstanceGroupManagerRequest(
            project=project,
            region=region,
            instance_group_manager=name,
        ),
    )
    assert mig
    return (scenario, mig)


@pytest.fixture(scope="module")
def instance_group_for_scenario(
    region_instance_groups_client: compute_v1.RegionInstanceGroupsClient,
    fixture_output: tuple[StatelessScenario, dict[str, Any]],
    instances_for_scenario: tuple[StatelessScenario, list[compute_v1.Instance]],  # noqa: ARG001 # Depend on BIG-IP VE onboarding to complete
) -> tuple[StatelessScenario, compute_v1.InstanceGroup]:
    """Return an InstanceGroup from the output."""
    scenario = fixture_output[0]
    output_values = fixture_output[1]
    self_link = cast("str", output_values["instance_group"])
    assert self_link
    match = re.search(DEFAULT_INSTANCE_GROUP_SELF_LINK_PATTERN, self_link)
    assert match
    project, region, name = match.groups()
    group = region_instance_groups_client.get(
        request=compute_v1.GetRegionInstanceGroupRequest(
            project=project,
            region=region,
            instance_group=name,
        ),
    )
    assert group
    return (scenario, group)


def test_output_values(
    project_id: str,
    region: str,
    fixture_output: tuple[StatelessScenario, dict[str, Any]],
) -> None:
    """Verify the fixture output meets expectations."""
    assert fixture_output is not None
    scenario = fixture_output[0]
    output_values = fixture_output[1]
    instance_group_manager = cast("str", output_values["instance_group_manager"])
    assert instance_group_manager
    assert re.search(
        pattern=f"projects/{project_id}/regions/{region}/instanceGroupManagers/{scenario!s}$",
        string=instance_group_manager,
    )
    instance_group = cast("str", output_values["instance_group"])
    assert instance_group
    assert re.search(
        pattern=f"projects/{project_id}/regions/{region}/instanceGroups/{scenario!s}$",
        string=instance_group,
    )


def test_instance_group_manager(
    project_id: str,
    region: str,
    instance_group_manager_for_scenario: tuple[StatelessScenario, compute_v1.InstanceGroupManager],
) -> None:
    """Raise an AssertionError if the regional MIG properties do not match expectations."""
    scenario = instance_group_manager_for_scenario[0]
    instance_group_manager = instance_group_manager_for_scenario[1]
    default_assert_instance_group_manager(
        instance_group_manager,
        base_instance_name_asserter=equal_asserter_builder(str(scenario)),
        instance_group_asserter=re_asserter_builder(
            f"projects/{project_id}/regions/{region}/instanceGroups/{scenario!s}$",
        ),
        instance_template_asserter=re_asserter_builder(
            f"projects/{project_id}/global/instanceTemplates/{scenario!s}[0-9]+$",
        ),
    )
    default_assert_instance_group_manager_all_instances_config(instance_group_manager.all_instances_config)
    default_assert_instance_group_manager_auto_healing_policies(instance_group_manager.auto_healing_policies)
    default_assert_instance_group_manager_actions_summary(instance_group_manager.current_actions)
    default_assert_distribution_policy(instance_group_manager.distribution_policy)
    default_assert_instance_group_manager_instance_flexibility_policy(
        instance_group_manager.instance_flexibility_policy,
    )
    default_assert_instance_group_manager_instance_lifecycle_policy(instance_group_manager.instance_lifecycle_policy)
    default_assert_named_ports(instance_group_manager.named_ports)
    default_assert_instance_group_manager_resource_policies(instance_group_manager.resource_policies)
    default_assert_instance_group_manager_standby_policy(instance_group_manager.standby_policy)
    default_assert_stateful_policy(instance_group_manager.stateful_policy)
    default_assert_instance_group_manager_status(instance_group_manager.status)
    default_assert_instance_group_manager_update_policy(instance_group_manager.update_policy)
    default_assert_instance_group_manager_versions(
        instance_group_manager.versions,
        instance_template_asserter=re_asserter_builder(
            f"projects/{project_id}/global/instanceTemplates/{scenario!s}[0-9]+$",
        ),
    )


def test_instance_group(
    instance_group_for_scenario: tuple[StatelessScenario, compute_v1.InstanceGroup],
) -> None:
    """Raise an AssertionError if the instance group properties do not match expectations."""
    instance_group = instance_group_for_scenario[1]
    default_assert_instance_group(instance_group)
    # These should be identical to those from instance group manager
    default_assert_named_ports(instance_group.named_ports)


def test_managed_instances(
    managed_instances_for_scenario: tuple[StatelessScenario, list[compute_v1.ManagedInstance]],
) -> None:
    """Raise an AssertionError if the instances associated with the regional MIG do not match expectations."""
    managed_instances = managed_instances_for_scenario[1]
    assert managed_instances
    assert len(managed_instances) == DEFAULT_TARGET_SIZE
    for instance in managed_instances:
        default_assert_managed_instance(instance)
        default_assert_managed_instance_instance_health(instance.instance_health)


def test_instances(
    guest_attributes_asserter: Callable[..., None],
    bigip_is_ready_asserter: Callable[..., None],
    instances_for_scenario: tuple[StatelessScenario, list[compute_v1.Instance]],
    sa_email: str,
    fixture_labels: dict[str, str],
    fixture_metadata: dict[str, str],
    subnet_ranges: list[ipaddress.IPv4Network],
) -> None:
    """Raise an AssertionError if the instances do not match expectations."""
    scenario = instances_for_scenario[0]
    instances = instances_for_scenario[1]
    for instance in instances:
        guest_attributes_asserter(instance)
        default_assert_instance(instance, hostname_asserter=unset_asserter)
        default_assert_labels(instance.labels, expected_labels=fixture_labels)
        default_assert_advanced_machine_features(instance.advanced_machine_features)
        default_assert_confidential_instance_config(instance.confidential_instance_config)
        default_assert_disks(instance.disks)
        default_assert_display_device(instance.display_device)
        default_assert_customer_encryption_key(instance.instance_encryption_key)
        default_assert_accelerator_configs(instance.guest_accelerators)
        default_assert_metadata(instance.metadata, expected_metadata=fixture_metadata)
        default_assert_network_interfaces(
            instance.network_interfaces,
            expected_subnets=subnet_ranges[: scenario.nic_count],
        )
        default_assert_network_performance_config(instance.network_performance_config)
        default_assert_reservation_affinity(instance.reservation_affinity)
        default_assert_resource_policies(instance.resource_policies)
        default_assert_resource_status(instance.resource_status)
        default_assert_scheduling(instance.scheduling)
        default_assert_service_accounts(
            instance.service_accounts,
            service_account_email_asserter=equal_asserter_builder(sa_email),
        )
        default_assert_shielded_instance_config(instance.shielded_instance_config)
        default_assert_shielded_instance_integrity_policy(instance.shielded_instance_integrity_policy)
        default_assert_customer_encryption_key(instance.source_machine_image_encryption_key)
        default_assert_tags(instance.tags)
        bigip_is_ready_asserter(instance=instance)
