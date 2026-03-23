"""Test fixture for stateful BIG-IP HA with only required values.

NOTE: Using a minimal config means all interfaces are configured without public IPs, and without the metadata tag to
enable guest attributes; host validation will not be performed.
"""

import ipaddress
import pathlib
import re
from collections.abc import Callable, Generator, MutableSequence
from typing import Any, cast

import pytest
from google.cloud import compute_v1

from tests import (
    DEFAULT_INSTANCE_NIC_TYPE,
    DEFAULT_TARGET_SIZE,
    default_assert_accelerator_configs,
    default_assert_advanced_machine_features,
    default_assert_confidential_instance_config,
    default_assert_customer_encryption_key,
    default_assert_disks,
    default_assert_display_device,
    default_assert_instance,
    default_assert_labels,
    default_assert_metadata,
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
    run_tf_in_workspace,
    unset_asserter,
)

FIXTURE_NAME = "root-min"


@pytest.fixture(scope="module")
def fixture_name(prefix: str) -> str:
    """Return the name to use for resources in this module."""
    return f"{prefix}-{FIXTURE_NAME}"


@pytest.fixture(scope="module")
def sa_email(service_account_builder: Callable[..., str], fixture_name: str) -> str:
    """Create a service account for this test case and return it's email identifier."""
    return service_account_builder(name=fixture_name, display_name="Minimal BIG-IP stateful HA")


@pytest.fixture(scope="module")
def subnet_ranges(
    subnet_ranges_builder: Callable[[int | None], list[ipaddress.IPv4Network]],
) -> list[ipaddress.IPv4Network]:
    """Return a list of subnet CIDRs for this test case."""
    return subnet_ranges_builder(2)


@pytest.fixture(scope="module")
def subnet_self_links(
    fixture_name: str,
    subnet_ranges: list[ipaddress.IPv4Network],
    network_builder: Callable[..., str],
    subnet_builder: Callable[..., str],
) -> list[str]:
    """Create testing VPC subnets for external and management interfaces, returning their self-links."""
    subnets: list[str] = []
    for i, cidr in enumerate(subnet_ranges):
        vpc_name = f"{fixture_name}-{i}"
        network_self_link = network_builder(name=vpc_name)
        subnets.append(subnet_builder(name=vpc_name, cidr=str(cidr), network_self_link=network_self_link))
    return subnets


@pytest.fixture(scope="module")
def fixture_output(
    project_id: str,
    sa_email: str,
    fixture_dir: Callable[[str], pathlib.Path],
    fixture_name: str,
    subnet_self_links: list[str],
) -> Generator[dict[str, Any]]:
    """Create a Compute Engine instance for the minimal values test case."""
    with run_tf_in_workspace(
        fixture=fixture_dir(fixture_name),
        tfvars={
            "prefix": fixture_name,
            "project_id": project_id,
            "service_account": sa_email,
            "interfaces": [
                {
                    "subnet_id": self_link,
                }
                for self_link in subnet_self_links
            ],
        },
    ) as output:
        yield output


def test_output_values(
    project_id: str,
    region: str,
    fixture_name: str,
    subnet_ranges: list[ipaddress.IPv4Network],
    fixture_output: dict[str, Any],
) -> None:
    """Verify the fixture output meets expectations."""
    assert fixture_output is not None
    expected_names = [
        f"{fixture_name}-01",
        f"{fixture_name}-02",
    ]
    self_links = cast("dict[str, str]", fixture_output["self_links"])
    assert self_links
    assert len(self_links) == len(expected_names)
    names = cast("list[str]", fixture_output["names"])
    assert names
    assert len(names) == len(expected_names)
    public_mgmt_ips = cast("dict[str, str]", fixture_output["public_mgmt_ips"])
    assert public_mgmt_ips
    assert len(public_mgmt_ips) == len(expected_names)
    private_mgmt_ips = cast("dict[str, str]", fixture_output["private_mgmt_ips"])
    assert private_mgmt_ips
    assert len(private_mgmt_ips) == len(expected_names)
    for name in expected_names:
        assert name in self_links
        assert re.search(f"projects/{project_id}/zones/{region}-[a-z]/instances/{name}$", self_links[name])
        assert name in names
        assert name in public_mgmt_ips
        assert public_mgmt_ips[name] == ""
        assert name in private_mgmt_ips
        private_mgmt_ip = ipaddress.IPv4Address(private_mgmt_ips[name])
        assert private_mgmt_ip.is_private
        assert private_mgmt_ip in subnet_ranges[1]
    instances_by_zone = cast("dict[str, list[str]]", fixture_output["instances_by_zone"])
    assert len(instances_by_zone) == len(expected_names)
    for zone, links in instances_by_zone.items():
        assert re.match(f"^{region}-[a-z]$", zone)
        assert len(links) == 1
    cluster_tag = cast("str", fixture_output["cluster_tag"])
    assert cluster_tag


@pytest.fixture(scope="module")
def instances(
    instances_builder: Callable[[list[str]], list[compute_v1.Instance]],
    fixture_output: dict[str, Any],
) -> list[compute_v1.Instance]:
    """Return a list of Compute Engine Instances from Terraform output."""
    self_links = cast("dict[str, str]", fixture_output["self_links"])
    assert self_links
    instances = list(instances_builder([self_link for _, self_link in self_links.items()]))
    assert len(instances) == DEFAULT_TARGET_SIZE
    return instances


def test_instances(
    subnet_ranges: list[ipaddress.IPv4Network],
    instances: list[compute_v1.Instance],
    sa_email: str,
    fixture_output: dict[str, Any],
) -> None:
    """Raise an AssertionError if the instances do not match expectations."""
    cluster_tag = cast("str", fixture_output["cluster_tag"])
    assert cluster_tag
    for instance in instances:
        default_assert_instance(instance, hostname_asserter=unset_asserter)
        default_assert_labels(instance.labels)
        default_assert_advanced_machine_features(instance.advanced_machine_features)
        default_assert_confidential_instance_config(instance.confidential_instance_config)
        default_assert_disks(instance.disks)
        default_assert_display_device(instance.display_device)
        default_assert_customer_encryption_key(instance.instance_encryption_key)
        default_assert_accelerator_configs(instance.guest_accelerators)
        default_assert_metadata(instance.metadata)
        assert_network_interfaces(instance.network_interfaces, expected_subnets=subnet_ranges)
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


def assert_network_interfaces(
    network_interfaces: MutableSequence[compute_v1.NetworkInterface] | None,
    expected_subnets: list[ipaddress.IPv4Network] | None = None,
) -> None:
    """Raise an AssertionError if the sequence of NetworkInterface objects does not meet expectations."""
    assert network_interfaces is not None
    if expected_subnets is not None:
        assert len(network_interfaces) == len(expected_subnets)
    else:
        assert len(network_interfaces) > 0
    for i, network_interface in enumerate(network_interfaces):
        assert len(network_interface.access_configs) == 0
        assert len(network_interface.alias_ip_ranges) == 0
        assert len(network_interface.ipv6_access_configs) == 0
        assert not network_interface.ipv6_address
        primary_ip = ipaddress.IPv4Address(network_interface.network_i_p)
        assert primary_ip
        assert primary_ip.is_private
        if expected_subnets is not None:
            assert primary_ip in expected_subnets[i]
        assert network_interface.nic_type == DEFAULT_INSTANCE_NIC_TYPE
        assert network_interface.stack_type == "IPV4_ONLY"
