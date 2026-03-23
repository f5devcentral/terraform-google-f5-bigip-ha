"""Test fixture for 1-NIC BIG-IP HA instance template with minimal required values."""

import ipaddress
import pathlib
import re
from collections.abc import Callable, Generator
from typing import Any, cast

import pytest
from google.cloud import compute_v1

from tests import (
    default_assert_accelerator_configs,
    default_assert_advanced_machine_features,
    default_assert_confidential_instance_config,
    default_assert_metadata,
    default_assert_network_performance_config,
    default_assert_reservation_affinity,
    default_assert_resource_manager_tags,
    default_assert_resource_policies,
    default_assert_scheduling,
    default_assert_service_accounts,
    default_assert_shielded_instance_config,
    default_assert_tags,
    equal_asserter_builder,
    run_tf_in_workspace,
)
from tests.template import (
    default_assert_disks,
    default_assert_instance_properties,
    default_assert_instance_template,
    default_assert_network_interfaces,
)

FIXTURE_NAME = "tmpl-min"


@pytest.fixture(scope="module")
def fixture_name(prefix: str) -> str:
    """Return the name to use for resources in this module."""
    return f"{prefix}-{FIXTURE_NAME}"


@pytest.fixture(scope="module")
def fixture_labels(labels: dict[str, str]) -> dict[str, str]:
    """Return a dict of labels for this test module."""
    return {"fixture": FIXTURE_NAME} | labels


# Instance templates can be created with a named service account that is not required to exist at template creation; use
# this to avoid creating a real service account for the test case.
@pytest.fixture(scope="module")
def sa_email(project_id: str, fixture_name: str) -> str:
    """Return a dummy service account email identifier."""
    return f"{fixture_name}@{project_id}.iam.gserviceaccount.com"


@pytest.fixture(scope="module")
def subnet_ranges(
    subnet_ranges_builder: Callable[[int | None], list[ipaddress.IPv4Network]],
) -> list[ipaddress.IPv4Network]:
    """Return a list of subnet CIDRs for this test case."""
    return subnet_ranges_builder(1)


@pytest.fixture(scope="module")
def subnet_self_links(
    fixture_name: str,
    subnet_ranges: list[ipaddress.IPv4Network],
    network_builder: Callable[..., str],
    subnet_builder: Callable[..., str],
) -> list[str]:
    """Create testing VPC subnets returning their self-links."""
    subnets: list[str] = []
    for i, cidr in enumerate(subnet_ranges):
        vpc_name = f"{fixture_name}-{i}"
        network_self_link = network_builder(name=vpc_name)
        subnets.append(subnet_builder(name=vpc_name, cidr=str(cidr), network_self_link=network_self_link))
    return subnets


@pytest.fixture(scope="module")
def fixture_output(
    template_fixture_dir: Callable[[str], pathlib.Path],
    project_id: str,
    fixture_name: str,
    sa_email: str,
    subnet_self_links: str,
) -> Generator[dict[str, Any]]:
    """Create a Compute Engine instance template for test case."""
    with run_tf_in_workspace(
        fixture=template_fixture_dir(FIXTURE_NAME),
        tfvars={
            "project_id": project_id,
            "prefix": fixture_name,
            "service_account": sa_email,
            "interfaces": [{"subnet_id": self_link} for self_link in subnet_self_links],
        },
    ) as output:
        yield output


def test_output_values(project_id: str, fixture_name: str, fixture_output: dict[str, Any]) -> None:
    """Verify the fixture output meets expectations."""
    assert fixture_output is not None
    self_link = cast("str", fixture_output["self_link"])
    assert self_link
    assert re.search(
        f"projects/{project_id}/global/instanceTemplates/{fixture_name}[0-9]+\\?uniqueId=[0-9]+$",
        self_link,
    )
    template_id = cast("str", fixture_output["id"])
    assert template_id
    assert re.search(f"projects/{project_id}/global/instanceTemplates/{fixture_name}[0-9]+$", template_id)
    name = cast("str", fixture_output["name"])
    assert name
    assert re.search(f"{fixture_name}[0-9]+$", name)


def test_instance_template(
    instance_templates_client: compute_v1.InstanceTemplatesClient,
    project_id: str,
    sa_email: str,
    fixture_output: dict[str, Any],
    subnet_ranges: list[ipaddress.IPv4Network],
) -> None:
    """Raise an AssertionError if the instance template does not match expectations."""
    name = cast("str", fixture_output["name"])
    assert name
    instance_template = instance_templates_client.get(
        request=compute_v1.GetInstanceTemplateRequest(
            project=project_id,
            instance_template=name,
        ),
    )
    default_assert_instance_template(
        instance_template,
        description_asserter=equal_asserter_builder("1-nic BIG-IP instance template for v21.0.0"),
    )
    default_assert_instance_properties(
        instance_template.properties,
        description_asserter=equal_asserter_builder("1-nic BIG-IP v21.0.0"),
    )
    default_assert_advanced_machine_features(instance_template.properties.advanced_machine_features)
    default_assert_confidential_instance_config(instance_template.properties.confidential_instance_config)
    default_assert_disks(
        instance_template.properties.disks,
    )
    default_assert_accelerator_configs(instance_template.properties.guest_accelerators)
    default_assert_metadata(instance_template.properties.metadata)
    default_assert_network_interfaces(
        instance_template.properties.network_interfaces,
        expected_subnets=subnet_ranges,
    )
    default_assert_network_performance_config(instance_template.properties.network_performance_config)
    default_assert_reservation_affinity(instance_template.properties.reservation_affinity)
    default_assert_resource_manager_tags(instance_template.properties.resource_manager_tags)
    default_assert_resource_policies(instance_template.properties.resource_policies)
    default_assert_scheduling(instance_template.properties.scheduling)
    default_assert_service_accounts(
        instance_template.properties.service_accounts,
        service_account_email_asserter=equal_asserter_builder(sa_email),
    )
    default_assert_shielded_instance_config(instance_template.properties.shielded_instance_config)
    default_assert_tags(instance_template.properties.tags)
