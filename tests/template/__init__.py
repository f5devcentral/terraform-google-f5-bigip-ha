"""Assertions common to template module test cases."""

import ipaddress
import re
from collections.abc import MutableSequence

from google.cloud import compute_v1

from tests import (
    DEFAULT_INSTANCE_BOOT_DISK_TYPE,
    DEFAULT_INSTANCE_DESCRIPTION_PATTERN,
    DEFAULT_INSTANCE_MACHINE_TYPE,
    DEFAULT_INSTANCE_NIC_TYPE,
    AsserterFunc,
    default_assert_customer_encryption_key,
    default_assert_labels,
    re_asserter_builder,
    unset_asserter,
)

DEFAULT_INSTANCE_TEMPLATE_DESCRIPTION_PATTERN = re.compile(
    r"[1-8]-nic BIG-IP instance template for v(?:1[567]|21)\.[0-9]+\.[0-9]+$",
)
DEFAULT_INSTANCE_TEMPLATE_IMAGE_SELF_LINK_PATTERN = re.compile(
    r"projects/f5-7626-networks-public/global/images/f5-bigip-.*$",
)
DEFAULT_INSTANCE_TEMPLATE_SELF_LINK_PATTERN = re.compile(
    r"projects/([a-z][a-z0-9-]{4,28}[a-z0-9])/global/instanceTemplates/([a-z](?:[a-z0-9-]*)?[0-9]+)(\?uniqueId=[0-9]+)?$",
)


def default_assert_instance_template(
    template: compute_v1.InstanceTemplate | None,
    description_asserter: AsserterFunc | None = None,
) -> None:
    """Raise an AssertionError if the InstanceTemplate object does not match expectations."""
    if description_asserter is None:
        description_asserter = re_asserter_builder(DEFAULT_INSTANCE_TEMPLATE_DESCRIPTION_PATTERN)
    assert template is not None
    description_asserter(template.description)
    assert not template.region
    assert not template.source_instance
    assert not template.source_instance_params


def default_assert_instance_properties(
    properties: compute_v1.InstanceProperties | None,
    description_asserter: AsserterFunc | None = None,
    expected_labels: dict[str, str] | None = None,
    expected_machine_type: str | None = None,
    expected_min_cpu_platform: str | None = None,
) -> None:
    """Raise an AssertionError if the Instance or InstanceProperties object does not meet common expectations."""
    if description_asserter is None:
        description_asserter = re_asserter_builder(DEFAULT_INSTANCE_DESCRIPTION_PATTERN)
    if expected_machine_type is None:
        expected_machine_type = DEFAULT_INSTANCE_MACHINE_TYPE
    assert properties is not None
    assert properties.can_ip_forward
    description_asserter(properties.description)
    assert not properties.key_revocation_action_type
    default_assert_labels(properties.labels, expected_labels=expected_labels)
    assert properties.machine_type.endswith(expected_machine_type)
    if expected_min_cpu_platform is not None:
        assert properties.min_cpu_platform == expected_min_cpu_platform
    else:
        assert not properties.min_cpu_platform
    assert not properties.private_ipv6_google_access


# Override as templates have a different set of disk properties than instances.
def default_assert_disks(
    disks: MutableSequence[compute_v1.AttachedDisk],
    image_asserter: AsserterFunc | None = None,
    disk_size_asserter: AsserterFunc | None = None,
    expected_boot_disk_type: str | None = None,
) -> None:
    """Raise an AssertionError if the sequence of AttachedDisks in an InstanceTemplate does not match expectations."""
    if expected_boot_disk_type is None:
        expected_boot_disk_type = DEFAULT_INSTANCE_BOOT_DISK_TYPE
    if image_asserter is None:
        image_asserter = re_asserter_builder(DEFAULT_INSTANCE_TEMPLATE_IMAGE_SELF_LINK_PATTERN)
    if disk_size_asserter is None:
        disk_size_asserter = unset_asserter
    assert disks is not None
    assert len(disks) == 1
    for i, disk in enumerate(disks):
        assert not disk.architecture
        assert disk.auto_delete
        assert disk.boot
        assert disk.device_name == "boot-disk"
        default_assert_customer_encryption_key(disk.disk_encryption_key)
        disk_size_asserter(disk.disk_size_gb)
        assert not disk.force_attach
        assert disk.guest_os_features is not None
        assert len(disk.guest_os_features) == 0
        assert disk.index == i
        assert disk.initialize_params is not None
        image_asserter(disk.initialize_params.source_image)
        assert not disk.interface
        assert disk.mode == "READ_WRITE"
        assert not disk.saved_state
        assert not disk.shielded_instance_initial_state
        assert not disk.source
        assert disk.type_ == "PERSISTENT"


def default_assert_network_interfaces(
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
        assert len(network_interface.access_configs) == 0
        assert len(network_interface.alias_ip_ranges) == 0
        assert len(network_interface.ipv6_access_configs) == 0
        assert not network_interface.ipv6_address
        assert not network_interface.network_i_p
        assert network_interface.nic_type == DEFAULT_INSTANCE_NIC_TYPE
        assert not network_interface.stack_type
