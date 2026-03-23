"""Test fixture for stateful BIG-IP HA deployment with multiple versions and NIC counts.

This test case will create stateful BIG-IP HA deployments using the root module for each BIG-IP version known to this
test package and NICs for [2, MAX_NIC_COUNT]. See the constants in __init__.py for current values.

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
    Scenario,
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
)

FIXTURE_NAME = "root-combo"


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
    return service_account_builder(name=fixture_name, display_name="Minimal BIG-IP stateful HA")


@pytest.fixture(scope="module")
def fixture_metadata(
    source_cidr: str,
) -> dict[str, str]:
    """Return a metadata dictionary with block-project-ssh-keys enabled, guest-attributes enabled, and a source CIDR."""
    return {
        "block-project-ssh-keys": "TRUE",
        "enable-guest-attributes": "TRUE",
        "source-cidr": source_cidr,
    }


@pytest.fixture(scope="module")
def subnet_ranges(
    subnet_ranges_builder: Callable[..., list[ipaddress.IPv4Network]],
) -> list[ipaddress.IPv4Network]:
    """Return a list of subnet CIDRs for this test case."""
    return subnet_ranges_builder(MAX_NIC_COUNT)


@pytest.fixture(scope="module")
def subnet_self_links(
    subnet_ranges: list[ipaddress.IPv4Network],
    network_builder: Callable[..., str],
    subnet_builder: Callable[..., str],
    allow_ingress_firewall_builder: Callable[..., str],
) -> list[str]:
    """Create testing VPC subnets for external and management interfaces, returning their self-links.

    NOTE: A firewall to allow access to management interface will be added.
    """
    subnets: list[str] = []
    for i, cidr in enumerate(subnet_ranges[:MAX_NIC_COUNT]):
        vpc_name = f"{FIXTURE_NAME}-{i}"
        network_self_link = network_builder(name=vpc_name)
        if i <= 1:
            allow_ingress_firewall_builder(network=network_self_link, name=vpc_name)
        subnets.append(subnet_builder(name=vpc_name, cidr=str(cidr), network_self_link=network_self_link))
    return subnets


@pytest.fixture(scope="module")
def common_tfvars(
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
        "metadata": fixture_metadata,
        "labels": fixture_labels,
        "host_domain": "example.com",
        "runtime_init_config": runtime_init_conf,
        "runtime_init_installer": {
            "skip_telemetry": True,
        },
    }


@pytest.fixture(
    scope="module",
    params=scenario_generator(Scenario),
    ids=scenario_id_builder,
)
def scenario(
    request: pytest.FixtureRequest,
    fixture_name: str,
    common_tfvars: dict[str, Any],
    subnet_self_links: list[str],
) -> Scenario:
    """Return a Scenario object for each combination of BIG-IP images under test and NIC counts."""
    scenario = cast("Scenario", request.param)
    scenario.prefix = fixture_name
    scenario.tfvars = common_tfvars | {
        "interfaces": [
            {
                "subnet_id": self_link,
                "public_ip": i == min(scenario.nic_count - 1, 1),
            }
            for i, self_link in enumerate(subnet_self_links)
            if i < scenario.nic_count
        ],
    }
    return scenario


@pytest.fixture(scope="module")
def fixture_output(
    fixture_dir: Callable[[str], pathlib.Path],
    scenario: Scenario,
) -> Generator[tuple[Scenario, dict[str, Any]]]:
    """Create a Compute Engine instance template for a test scenario."""
    with run_tf_in_workspace(
        fixture=fixture_dir(str(scenario)),
        tfvars=scenario.tfvars,
    ) as output:
        yield (scenario, output)


@pytest.fixture(scope="module")
def instances(
    instances_builder: Callable[[list[str]], list[compute_v1.Instance]],
    wait_for_onboarding_complete: Callable[..., compute_v1.Instance],
    fixture_output: tuple[Scenario, dict[str, Any]],
) -> list[compute_v1.Instance]:
    """Return a list of Compute Engine Instances from Terraform output."""
    self_links = cast("dict[str, str]", fixture_output[1]["self_links"])
    assert self_links
    instances = [
        wait_for_onboarding_complete(instance)
        for instance in instances_builder([self_link for _, self_link in self_links.items()])
    ]
    assert len(instances) == DEFAULT_TARGET_SIZE
    return instances


def test_output_values(
    project_id: str,
    region: str,
    subnet_ranges: list[ipaddress.IPv4Network],
    fixture_output: tuple[Scenario, dict[str, Any]],
) -> None:
    """Verify the fixture output meets expectations."""
    assert fixture_output is not None
    expected_names = fixture_output[0].expected_names
    output_values = fixture_output[1]
    self_links = cast("dict[str, str]", output_values["self_links"])
    assert self_links
    assert len(self_links) == len(expected_names)
    names = cast("list[str]", output_values["names"])
    assert names
    assert len(names) == len(expected_names)
    public_mgmt_ips = cast("dict[str, str]", output_values["public_mgmt_ips"])
    assert public_mgmt_ips
    assert len(public_mgmt_ips) == len(expected_names)
    private_mgmt_ips = cast("dict[str, str]", output_values["private_mgmt_ips"])
    assert private_mgmt_ips
    assert len(private_mgmt_ips) == len(expected_names)
    for name in expected_names:
        assert name in self_links
        assert re.search(f"projects/{project_id}/zones/{region}-[a-z]/instances/{name}$", self_links[name])
        assert name in names
        assert name in public_mgmt_ips
        public_mgmt_ip = ipaddress.IPv4Address(public_mgmt_ips[name])
        assert not public_mgmt_ip.is_private
        assert name in private_mgmt_ips
        private_mgmt_ip = ipaddress.IPv4Address(private_mgmt_ips[name])
        assert private_mgmt_ip.is_private
        assert private_mgmt_ip in subnet_ranges[1]
    instances_by_zone = cast("dict[str, list[str]]", output_values["instances_by_zone"])
    assert len(instances_by_zone) == len(expected_names)
    for zone, links in instances_by_zone.items():
        assert re.match(f"^{region}-[a-z]$", zone)
        assert len(links) == 1
    cluster_tag = cast("str", output_values["cluster_tag"])
    assert cluster_tag


def test_instances(
    guest_attributes_asserter: Callable[..., None],
    bigip_is_ready_asserter: Callable[[compute_v1.Instance], None],
    active_standby_asserter: Callable[[list[compute_v1.Instance]], None],
    instances: list[compute_v1.Instance],
    sa_email: str,
    fixture_labels: dict[str, str],
    fixture_metadata: dict[str, str],
    fixture_output: tuple[Scenario, dict[str, Any]],
    subnet_ranges: list[ipaddress.IPv4Network],
) -> None:
    """Raise an AssertionError if the instances do not match expectations."""
    scenario = fixture_output[0]
    output_values = fixture_output[1]
    cluster_tag = cast("str", output_values["cluster_tag"])
    assert cluster_tag
    for instance in instances:
        guest_attributes_asserter(instance)
        default_assert_instance(
            instance,
            description_asserter=equal_asserter_builder(scenario.expected_description),
            hostname_asserter=re_asserter_builder(f"{scenario!s}-0[12].example.com$"),
        )
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
        default_assert_tags(instance.tags, expected_tags=[cluster_tag])
        bigip_is_ready_asserter(instance)
    active_standby_asserter(instances)
