"""Test fixture for stateful-nlb example using local module sources."""

import ipaddress
import pathlib
from collections.abc import Callable, Generator
from typing import Any, cast

import pytest
import requests
from google.cloud import compute_v1

from tests import DEFAULT_TARGET_SIZE, run_tf_in_workspace

FIXTURE_NAME = "ex-root-nlb"


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
    allow_ingress_firewall_builder: Callable[..., str],
) -> list[str]:
    """Create testing VPC subnets for external, management, and internal interfaces, returning their self-links."""
    subnets: list[str] = []
    for i, cidr in enumerate(subnet_ranges):
        vpc_name = f"{fixture_name}-{i}"
        network_self_link = network_builder(name=vpc_name)
        if i == 1:
            allow_ingress_firewall_builder(network=network_self_link, name=vpc_name)
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
) -> Generator[dict[str, Any]]:
    """Create the example resources."""
    with run_tf_in_workspace(
        fixture=fixture_dir(name=fixture_name, example_name="stateful-nlb"),
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
        },
    ) as output:
        yield output


@pytest.fixture(scope="module")
def instances(
    instances_builder: Callable[[list[str]], list[compute_v1.Instance]],
    wait_for_onboarding_complete: Callable[..., compute_v1.Instance],
    fixture_output: dict[str, Any],
) -> list[compute_v1.Instance]:
    """Return a list of Compute Engine Instances from Terraform output."""
    self_links = cast("dict[str, str]", fixture_output["self_links"])
    assert self_links
    instances = [
        wait_for_onboarding_complete(instance)
        for instance in instances_builder([self_link for _, self_link in self_links.items()])
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


def test_instances(
    bigip_is_ready_asserter: Callable[..., None],
    active_standby_asserter: Callable[..., None],
    admin_password: str,
    instances: list[compute_v1.Instance],
) -> None:
    """Raise an AssertionError if the instances do not match expectations."""
    for instance in instances:
        bigip_is_ready_asserter(instance=instance, password=admin_password)
    active_standby_asserter(instances=instances, password=admin_password)


def test_vip(
    project_id: str,
    region: str,
    fixture_name: str,
    wait_for_target_pool_healthy: Callable[..., None],
    fixture_output: dict[str, Any],
) -> None:
    """Verify that the VIP returns data."""
    assert fixture_output is not None
    vip = cast("str", fixture_output["vip"])
    assert vip
    # The example does not output the target pool self-link, but it should match the fixture_name
    wait_for_target_pool_healthy(self_link=f"projects/{project_id}/regions/{region}/targetPools/{fixture_name}")
    response = requests.get(url=f"https://{vip}/", verify=False)
    assert response.status_code == requests.codes["ok"]
    assert response.json
