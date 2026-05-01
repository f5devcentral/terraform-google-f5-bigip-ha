"""Test fixture for stateless-nlb example using local module sources."""

import ipaddress
import pathlib
import re
from collections.abc import Callable, Generator
from typing import Any, cast

import pytest
import requests
from google.cloud import compute_v1

from tests import DEFAULT_TARGET_SIZE, run_tf_in_workspace
from tests.stateless import DEFAULT_INSTANCE_GROUP_MANAGER_SELF_LINK_PATTERN, DEFAULT_INSTANCE_GROUP_SELF_LINK_PATTERN

FIXTURE_NAME = "ex-sles-nlb"


@pytest.fixture(scope="module")
def fixture_name(prefix: str) -> str:
    """Return the name to use for resources in this module."""
    return f"{prefix}-{FIXTURE_NAME}"


@pytest.fixture(scope="module")
def fixture_labels(fixture_name: str, labels: dict[str, str]) -> dict[str, str]:
    """Return a dict of labels for this test module."""
    return {"fixture": fixture_name} | labels


@pytest.fixture(scope="module")
def subnet_ranges(
    subnet_ranges_builder: Callable[[int | None], list[ipaddress.IPv4Network]],
) -> list[ipaddress.IPv4Network]:
    """Return a list of subnet CIDRs for this test case."""
    return subnet_ranges_builder(3)


@pytest.fixture(scope="module")
def subnet_self_links(
    fixture_name: str,
    subnet_ranges: list[ipaddress.IPv4Network],
    network_builder: Callable[..., str],
    subnet_builder: Callable[..., str],
) -> list[str]:
    """Create testing VPC subnets for external, management, and internal interfaces, returning their self-links."""
    subnets: list[str] = []
    for i, cidr in enumerate(subnet_ranges):
        vpc_name = f"{fixture_name}-{i}"
        network_self_link = network_builder(name=vpc_name)
        subnets.append(subnet_builder(name=vpc_name, cidr=str(cidr), network_self_link=network_self_link))
    return subnets


@pytest.fixture(scope="module")
def fixture_output(
    project_id: str,
    region: str,
    source_cidr: str,
    fixture_dir: Callable[..., pathlib.Path],
    fixture_name: str,
    fixture_labels: dict[str, str],
    subnet_self_links: list[str],
    wait_for_instance_group_manager_deleted: Callable[..., None],
) -> Generator[dict[str, Any]]:
    """Create the example resources."""
    with run_tf_in_workspace(
        fixture=fixture_dir(name=fixture_name, example_name="stateless-nlb"),
        tfvars={
            "name": fixture_name,
            "project_id": project_id,
            "region": region,
            "labels": fixture_labels,
            "interfaces": [
                {
                    "subnet_id": self_link,
                    "public_ip": i == 1,  # Make sure there's a public IP assigned to management for testing
                }
                for i, self_link in enumerate(subnet_self_links)
            ],
            "allowlist_cidrs": [
                source_cidr,
            ],
            "metadata": {
                "block-project-ssh-keys": "TRUE",
                "enable-guest-attributes": "TRUE",
            },
            "mgmt_allowlist_cidrs": [
                source_cidr,
            ],
        },
    ) as output:
        self_link = cast("str", output["instance_group_manager"])
        yield output
    wait_for_instance_group_manager_deleted(self_link)


@pytest.fixture(scope="module")
def managed_instances(
    region_instance_group_managers_client: compute_v1.RegionInstanceGroupManagersClient,
    fixture_output: dict[str, Any],
) -> list[compute_v1.ManagedInstance]:
    """Return the list of Compute Engine ManagedInstances."""
    self_link = cast("str", fixture_output["instance_group_manager"])
    assert self_link
    match = re.search(DEFAULT_INSTANCE_GROUP_MANAGER_SELF_LINK_PATTERN, self_link)
    assert match
    project, region, name = match.groups()
    return list(
        region_instance_group_managers_client.list_managed_instances(
            request=compute_v1.ListManagedInstancesRegionInstanceGroupManagersRequest(
                project=project,
                region=region,
                instance_group_manager=name,
            ),
        ),
    )


@pytest.fixture(scope="module")
def instances(
    instances_builder: Callable[[list[str]], list[compute_v1.Instance]],
    wait_for_onboarding_complete: Callable[..., compute_v1.Instance],
    managed_instances: list[compute_v1.ManagedInstance],
) -> list[compute_v1.Instance]:
    """Return a list of Compute Engine Instances from ManagedInstances list."""
    instances = [
        wait_for_onboarding_complete(instance)
        for instance in instances_builder([managed_instance.instance for managed_instance in managed_instances])
    ]
    assert len(instances) == DEFAULT_TARGET_SIZE
    return instances


@pytest.fixture(scope="module")
def admin_password(
    secret_retriever: Callable[..., bytes],
    fixture_output: dict[str, Any],
) -> str:
    """Return the BIG-IP admin password from Secret Manager."""
    secret_id = cast("str", fixture_output["admin_password_secret_id"])
    assert secret_id
    return secret_retriever(name=secret_id).decode(encoding="utf-8")


def test_output_values(
    fixture_output: dict[str, Any],
) -> None:
    """Verify the fixture output meets expectations."""
    assert fixture_output is not None
    vip = cast("str", fixture_output["vip"])
    assert vip
    address = ipaddress.IPv4Address(vip)
    assert address
    assert address.is_global
    secret_id = cast("str", fixture_output["admin_password_secret_id"])
    assert secret_id
    instance_group_manager_self_link = cast("str", fixture_output["instance_group_manager"])
    assert instance_group_manager_self_link
    assert re.search(DEFAULT_INSTANCE_GROUP_MANAGER_SELF_LINK_PATTERN, instance_group_manager_self_link)
    instance_group_self_link = cast("str", fixture_output["instance_group"])
    assert instance_group_self_link
    assert re.search(DEFAULT_INSTANCE_GROUP_SELF_LINK_PATTERN, instance_group_self_link)


def test_instances(
    bigip_is_ready_asserter: Callable[..., None],
    all_standalone_asserter: Callable[..., None],
    admin_password: str,
    instances: list[compute_v1.Instance],
) -> None:
    """Raise an AssertionError if the instances do not match expectations."""
    for instance in instances:
        bigip_is_ready_asserter(instance=instance, password=admin_password)
    all_standalone_asserter(instances=instances, password=admin_password)


def test_vip(
    project_id: str,
    region: str,
    fixture_name: str,
    wait_for_backend_service_healthy: Callable[..., None],
    fixture_output: dict[str, Any],
) -> None:
    """Verify that the VIP returns data."""
    assert fixture_output is not None
    vip = cast("str", fixture_output["vip"])
    assert vip
    # The example does not output the backend service self-link, but it should match the fixture_name
    wait_for_backend_service_healthy(self_link=f"projects/{project_id}/regions/{region}/backendServices/{fixture_name}")
    response = requests.get(url=f"https://{vip}/", verify=False)
    assert response.status_code == requests.codes["ok"]
    assert response.json
