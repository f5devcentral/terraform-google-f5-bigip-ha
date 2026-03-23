"""Test fixture for 8-NIC BIG-IP HA instance template with explicit values for all variables.

NOTE: The image is deliberately chosen to be a Google image so that gvNIC option can be asserted.
"""

import ipaddress
import pathlib
import re
from collections.abc import Callable, Generator, MutableSequence
from typing import Any, cast

import pytest
from google.cloud import compute_v1

from tests import (
    MAX_NIC_COUNT,
    default_assert_accelerator_configs,
    default_assert_advanced_machine_features,
    default_assert_confidential_instance_config,
    default_assert_network_performance_config,
    default_assert_reservation_affinity,
    default_assert_resource_manager_tags,
    default_assert_resource_policies,
    default_assert_service_accounts,
    default_assert_shielded_instance_config,
    default_assert_tags,
    equal_asserter_builder,
    re_asserter_builder,
    run_tf_in_workspace,
)
from tests.template import (
    default_assert_disks,
    default_assert_instance_properties,
    default_assert_instance_template,
)

FIXTURE_NAME = "tmpl-all"
FIXTURE_DESCRIPTION = "BIG-IP HA template test with all the things"
FIXTURE_DISK_SIZE_GB = 100
FIXTURE_DISK_TYPE = "pd-balanced"
FIXTURE_IMAGE = "projects/debian-cloud/global/images/debian-12-bookworm-v20251111"
FIXTURE_INSTANCE_DESCRIPTION = "BIG-IP HA template test"
FIXTURE_MACHINE_TYPE = "n2-standard-16"
FIXTURE_MIN_CPU_PLATFORM = "Intel Haswell"
FIXTURE_NETWORK_TAGS = [
    FIXTURE_NAME,
]
FIXTURE_RUNTIME_INIT_INSTALLER = {
    "url": "https://invalid/url",
    "sha256sum": "1234567890abcdef",
    "skip_telemetry": True,
    "skip_toolchain_metadata_sync": True,
    "skip_verify": True,
    "verify_gpg_key_url": "https://invalid/url",
}


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
def fixture_metadata() -> dict[str, str]:
    """Return a metadata dictionary with block-project-ssh-keys enabled, an instance SSH key, and minimal user-data."""
    return {
        "block-project-ssh-keys": "TRUE",
        "enable-guest-attributes": "TRUE",
        "user-data": "#!/bin/sh\necho Hello\n",
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
    template_fixture_dir: Callable[[str], pathlib.Path],
    project_id: str,
    runtime_init_conf: str,
    fixture_name: str,
    fixture_labels: dict[str, str],
    fixture_metadata: dict[str, str],
    sa_email: str,
    subnet_self_links: str,
) -> Generator[dict[str, Any]]:
    """Create a Compute Engine instance template for test case."""
    with run_tf_in_workspace(
        fixture=template_fixture_dir(FIXTURE_NAME),
        tfvars={
            "project_id": project_id,
            "prefix": fixture_name,
            "description": FIXTURE_DESCRIPTION,
            "instance_description": FIXTURE_INSTANCE_DESCRIPTION,
            "min_cpu_platform": FIXTURE_MIN_CPU_PLATFORM,
            "machine_type": FIXTURE_MACHINE_TYPE,
            "automatic_restart": True,
            "preemptible": True,
            "image": FIXTURE_IMAGE,
            "disk_type": FIXTURE_DISK_TYPE,
            "disk_size_gb": FIXTURE_DISK_SIZE_GB,
            "interfaces": [
                {
                    "subnet_id": self_link,
                    "public_ip": True,
                    "nic_type": "GVNIC",
                }
                for self_link in subnet_self_links
            ],
            "management_interface_index": 0,
            "labels": fixture_labels,
            "service_account": sa_email,
            "metadata": fixture_metadata,
            "network_tags": FIXTURE_NETWORK_TAGS,
            "runtime_init_config": runtime_init_conf,
            "runtime_init_installer": FIXTURE_RUNTIME_INIT_INSTALLER,
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
    fixture_labels: dict[str, str],
    fixture_metadata: dict[str, str],
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
        description_asserter=equal_asserter_builder(FIXTURE_DESCRIPTION),
    )
    default_assert_instance_properties(
        instance_template.properties,
        description_asserter=equal_asserter_builder(FIXTURE_INSTANCE_DESCRIPTION),
        expected_labels=fixture_labels,
        expected_machine_type=FIXTURE_MACHINE_TYPE,
        expected_min_cpu_platform=FIXTURE_MIN_CPU_PLATFORM,
    )
    default_assert_advanced_machine_features(instance_template.properties.advanced_machine_features)
    default_assert_confidential_instance_config(instance_template.properties.confidential_instance_config)
    default_assert_disks(
        instance_template.properties.disks,
        image_asserter=re_asserter_builder(f"{FIXTURE_IMAGE}$"),
        disk_size_asserter=equal_asserter_builder(FIXTURE_DISK_SIZE_GB),
        expected_boot_disk_type=FIXTURE_DISK_TYPE,
    )
    default_assert_accelerator_configs(instance_template.properties.guest_accelerators)
    assert_metadata(instance_template.properties.metadata, expected_metadata=fixture_metadata)
    assert_network_interfaces(instance_template.properties.network_interfaces, expected_subnets=subnet_ranges)
    default_assert_network_performance_config(instance_template.properties.network_performance_config)
    default_assert_reservation_affinity(instance_template.properties.reservation_affinity)
    default_assert_resource_manager_tags(instance_template.properties.resource_manager_tags)
    default_assert_resource_policies(instance_template.properties.resource_policies)
    assert_scheduling(instance_template.properties.scheduling)
    default_assert_service_accounts(
        instance_template.properties.service_accounts,
        service_account_email_asserter=equal_asserter_builder(sa_email),
    )
    default_assert_shielded_instance_config(instance_template.properties.shielded_instance_config)
    default_assert_tags(instance_template.properties.tags)


def assert_metadata(
    metadata: compute_v1.Metadata | None,
    expected_metadata: dict[str, str] | None = None,
) -> None:
    """Raise an error if the Metadata object does not match expectations."""
    if expected_metadata is None:
        expected_metadata = {}
    assert metadata is not None
    metadata_dict = {item.key: item.value for item in metadata.items}
    assert all(item in metadata_dict.items() for item in expected_metadata.items())
    assert "user-data" in metadata_dict
    assert metadata_dict["user-data"] == "#!/bin/sh\necho Hello\n"


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
    for network_interface in network_interfaces:
        assert len(network_interface.access_configs) == 1
        for access_config in network_interface.access_configs:
            assert access_config is not None
            assert access_config.type_ == "ONE_TO_ONE_NAT"
            assert not access_config.nat_i_p
            assert access_config.network_tier == "PREMIUM"
        assert len(network_interface.alias_ip_ranges) == 0
        assert len(network_interface.ipv6_access_configs) == 0
        assert not network_interface.ipv6_address
        assert not network_interface.network_i_p
        assert network_interface.nic_type == "GVNIC"
        assert not network_interface.stack_type


def assert_scheduling(scheduling: compute_v1.Scheduling | None = None) -> None:
    """Raise an AssertionError if the Scheduling object does not meet expectations."""
    assert scheduling is not None
    assert not scheduling.automatic_restart
    assert not scheduling.availability_domain
    assert not scheduling.host_error_timeout_seconds
    assert not scheduling.instance_termination_action
    assert not scheduling.local_ssd_recovery_timeout.nanos
    assert not scheduling.local_ssd_recovery_timeout.seconds
    assert not scheduling.max_run_duration.nanos
    assert not scheduling.max_run_duration.seconds
    assert not scheduling.min_node_cpus
    assert len(scheduling.node_affinities) == 0
    assert scheduling.on_host_maintenance == "TERMINATE"
    assert not scheduling.on_instance_stop_action.discard_local_ssd
    assert scheduling.preemptible
    assert not scheduling.provisioning_model
    assert not scheduling.skip_guest_os_shutdown
    assert not scheduling.termination_time
