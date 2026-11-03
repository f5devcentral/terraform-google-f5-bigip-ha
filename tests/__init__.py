"""Define functions common to all test cases in the tests namespace."""

import ipaddress
import itertools
import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Generator, MutableMapping, MutableSequence
from contextlib import contextmanager
from datetime import timedelta
from operator import itemgetter
from typing import Any

import jsonschema
import referencing
import requests
import yaml
from google.cloud import compute_v1

type AsserterFunc = Callable[[int | str | None], None]

# This must match the value hard-coded in the runtime-init files.
ADMIN_USER_PASSWORD = "3408ytqe^f23"  # spell-checker: disable-line

# The BIG-IP version and image to test
BIG_IP_IMAGES = {
    "21.1.0": "projects/f5-7626-networks-public/global/images/f5-bigip-21-1-0-0-0-payg-good-1gbps-260504135337",
    "21.0.0": "projects/f5-7626-networks-public/global/images/f5-bigip-21-0-0-1-0-0-13-payg-good-1gbps-260128095422",
    "17.5.1": "projects/f5-7626-networks-public/global/images/f5-bigip-17-5-1-5-0-0-6-payg-good-1gbps-260227021543",
    "16.1.6": "projects/f5-7626-networks-public/global/images/f5-bigip-16-1-6-1-0-0-11-payg-good-1gbps-251008153005",
    "15.1.10": "projects/f5-7626-networks-public/global/images/f5-bigip-15-1-10-8-0-0-30-payg-good-1gbps-251008214435",
}

# Test scenarios will be built that are the product of BIG-IP versions and various NIC assignments; since these tests
# are not end-to-end with valid origin servers attached to 'internal' interfaces there is little difference from a
# testing perspective between a scenario for BIG-IP with 3 NICs and with 4 or more NICs. Setting this value
# to 3 by default removes the need to build 5 VPC networks as a prerequisite for each test case, and 5 HA BIG-IP
# clusters per BIG-IP version under test.
MAX_NIC_COUNT = 3

DEFAULT_TARGET_SIZE = 2
DEFAULT_INSTANCE_SELF_LINK_PATTERN = re.compile(
    r"projects/([a-z][a-z0-9-]{4,28}[a-z0-9])/zones/([a-z][a-z-]+[0-9]-[a-z])/instances/([a-z](?:[a-z0-9-]{0,61}[a-z0-9])?)$",
)
DEFAULT_INSTANCE_BOOT_DISK_TYPE = "pd-ssd"
DEFAULT_INSTANCE_DESCRIPTION_PATTERN = re.compile(r"[1-8]-nic BIG-IP v(?:1[567]|21)\.[0-9]+\.[0-9]+$")
DEFAULT_INSTANCE_EXPECTED_STATUS = "RUNNING"
DEFAULT_INSTANCE_NAME_PATTERN = re.compile(r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?")
DEFAULT_INSTANCE_HOSTNAME_PATTERN = re.compile(
    r"[a-z][a-z0-9_-]{0,62}\.(?:[a-z]{2,20}-[a-z]{4,20}[0-9]+-[a-z]\.)?\.[a-z][a-z0-9-]{4,28}[a-z0-9].internal",
)
DEFAULT_INSTANCE_MACHINE_TYPE = "n1-standard-8"
DEFAULT_INSTANCE_NIC_TYPE = "VIRTIO_NET"
DEFAULT_INSTANCE_SERVICE_ACCOUNT_EMAIL_PATTERN = re.compile(
    r"(?:[a-z][a-z0-9-]{4,28}[a-z0-9]@[a-z][a-z0-9-]{4,28}[a-z0-9]\.iam|[0-9]+-compute@developer)\.gserviceaccount\.com$",
)

DEFAULT_WAIT_FOR_TIMEOUT = timedelta(seconds=1200)


def _schema_fetcher(uri: str) -> referencing.Resource:
    """Return a JSON Schema resource from URI."""
    return referencing.Resource.from_contents(requests.get(uri).json())


_registry = referencing.Registry(retrieve=_schema_fetcher)
_cloud_init_validator = jsonschema.Draft4Validator(
    schema={
        "$ref": "https://raw.githubusercontent.com/canonical/cloud-init/main/cloudinit/config/schemas/versions.schema.cloud-config.json",
    },
    registry=_registry,
)


def cloud_config_asserter(value: int | str | None) -> None:
    """Raise an AssertionError if value cannot be parsed and validated against Cloud Config JSON Schema."""
    assert isinstance(value, str)
    cloud_init = yaml.safe_load(value)
    assert cloud_init
    _cloud_init_validator.validate(cloud_init)


def re_asserter_builder(pattern: str | re.Pattern[str]) -> AsserterFunc:
    """Build an asserter for supplied regex."""
    if isinstance(pattern, str):
        pattern = re.compile(pattern)

    def _asserter(value: int | str | None) -> None:
        """Raise an AssertionError if value is not a string or does not match regex."""
        assert value is not None
        assert isinstance(value, str)
        assert re.search(pattern=pattern, string=value)

    return _asserter


def unset_asserter(value: int | str | None) -> None:
    """Raise an AssertionError if the value is anything other than falsy."""
    assert not value


def equal_asserter_builder(expected: int | str | None) -> AsserterFunc:
    """Return a function that can test the supplied value is equal to expected value."""

    def _asserter(value: int | str | None) -> None:
        """Raise an AssertionError if the value does not meet expectations."""
        assert value == expected

    return _asserter


def minimum_int_asserter_builder(limit: int) -> AsserterFunc:
    """Return a function that can test the supplied value is >= limit, where limit is a positive integer >= 0."""
    assert limit >= 0

    def _asserter(value: int | str | None) -> None:
        """Raise an AssertionError if the value is not a positive integer greater than limit."""
        assert value is not None
        assert isinstance(value, int)
        assert value >= limit

    return _asserter


def maximum_int_asserter_builder(limit: int) -> AsserterFunc:
    """Return a function that can test the supplied value is 0 <= value <= limit, where limit is > 0."""
    assert limit > 0

    def _asserter(value: int | str | None) -> None:
        """Raise an AssertionError if the value > 0 and <= limit."""
        assert value is not None
        assert isinstance(value, int)
        assert value >= 0
        assert value <= limit

    return _asserter


def skip_destroy_phase() -> bool:
    """Determine if resource destroy phase should be skipped for successful fixtures."""
    return os.getenv("TEST_SKIP_DESTROY_PHASE", "False").lower() in ["true", "t", "yes", "y", "1"]


def get_tf_command() -> str:
    """Return an explicit command to use for module execution or the first tofu or terraform binary found in PATH.

    NOTE: Preference will be given to the value of environment variable TEST_TF_COMMAND.
    """
    tf_command = os.getenv("TEST_TF_COMMAND") or shutil.which("tofu") or shutil.which("terraform")
    assert tf_command, "A tofu or terraform binary could not be determined"
    return tf_command


@contextmanager
def run_tf_in_workspace(
    fixture: pathlib.Path,
    tfvars: dict[str, Any] | None,
    workspace: str | None = None,
    tf_command: str | None = None,
) -> Generator[dict[str, Any]]:
    """Execute terraform/tofu fixture lifecycle in an optional workspace, yielding the output post-apply.

    NOTE: Resources will not be destroyed if the test case raises an error.
    """
    if tfvars is None:
        tfvars = {}
    if not tf_command:
        tf_command = get_tf_command()
    if workspace is not None and workspace != "":
        subprocess.run(
            [
                tf_command,
                f"-chdir={fixture!s}",
                "workspace",
                "select",
                "-or-create",
                workspace,
            ],
            check=True,
            capture_output=True,
        )
    subprocess.run(
        [
            tf_command,
            f"-chdir={fixture!s}",
            "init",
            "-no-color",
            "-input=false",
        ],
        check=True,
        capture_output=True,
    )
    with tempfile.NamedTemporaryFile(
        mode="w",
        prefix="tfvars",
        suffix=".json",
        encoding="utf-8",
        delete_on_close=False,
        delete=True,
    ) as tfvar_file:
        json.dump(tfvars, tfvar_file, ensure_ascii=False, indent=2)
        tfvar_file.close()
        # Execute plan then apply with a common plan file.
        with tempfile.NamedTemporaryFile(
            mode="w+b",
            prefix="tf",
            suffix=".plan",
            delete_on_close=False,
            delete=True,
        ) as plan_file:
            plan_file.close()
            subprocess.run(
                [
                    tf_command,
                    f"-chdir={fixture!s}",
                    "plan",
                    "-no-color",
                    "-input=false",
                    f"-var-file={tfvar_file.name}",
                    f"-out={plan_file.name}",
                ],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                args=[
                    tf_command,
                    f"-chdir={fixture!s}",
                    "apply",
                    "-no-color",
                    "-input=false",
                    "-auto-approve",
                    plan_file.name,
                ],
                check=True,
                capture_output=True,
            )

        # Run plan again with -detailed-exitcode flag, which will only return an exit code of 0 if there are no further
        # changes. This is to find subtle issues in the Terraform declaration which inadvertently triggers unexpected
        # resource updates or recreations.
        subprocess.run(
            [
                tf_command,
                f"-chdir={fixture!s}",
                "plan",
                "-no-color",
                "-input=false",
                "-detailed-exitcode",
                f"-var-file={tfvar_file.name}",
            ],
            check=True,
            capture_output=True,
        )
        output = subprocess.run(
            [
                tf_command,
                f"-chdir={fixture!s}",
                "output",
                "-no-color",
                "-json",
            ],
            check=True,
            capture_output=True,
        )
        try:
            yield {k: v["value"] for k, v in json.loads(output.stdout).items()}
            if not skip_destroy_phase():
                subprocess.run(
                    [
                        tf_command,
                        f"-chdir={fixture!s}",
                        "destroy",
                        "-no-color",
                        "-input=false",
                        "-auto-approve",
                        f"-var-file={tfvar_file.name}",
                    ],
                    check=True,
                    capture_output=True,
                )
        finally:
            subprocess.run(
                [
                    tf_command,
                    f"-chdir={fixture!s}",
                    "workspace",
                    "select",
                    "default",
                ],
                check=True,
                capture_output=True,
            )


@contextmanager
def run_tf_test(
    fixture: pathlib.Path,
    tfvars: dict[str, Any] | None = None,
    workspace: str | None = None,
    tf_command: str | None = None,
) -> Generator[list[dict[str, Any]]]:
    """Execute terraform/tofu test lifecycle in an optional workspace, yielding the output as a JSON array."""
    if tfvars is None:
        tfvars = {}
    if not tf_command:
        tf_command = get_tf_command()
    if workspace is not None and workspace != "":
        subprocess.run(
            [
                tf_command,
                f"-chdir={fixture!s}",
                "workspace",
                "select",
                "-or-create",
                workspace,
            ],
            check=True,
            capture_output=True,
        )
    subprocess.run(
        [
            tf_command,
            f"-chdir={fixture!s}",
            "init",
            "-no-color",
            "-input=false",
        ],
        check=True,
        capture_output=True,
    )
    with tempfile.NamedTemporaryFile(
        mode="w",
        prefix="tfvars",
        suffix=".json",
        encoding="utf-8",
        delete_on_close=False,
        delete=False,
    ) as tfvar_file:
        json.dump(tfvars, tfvar_file, ensure_ascii=False, indent=2)
        tfvar_file.close()
        output = subprocess.run(
            [
                tf_command,
                f"-chdir={fixture!s}",
                "test",
                "-json",
                f"-var-file={tfvar_file.name}",
            ],
            check=True,
            capture_output=True,
        )
        yield [json.loads(line) for line in output.stdout.splitlines()]


def default_assert_instance(
    instance: compute_v1.Instance | None,
    description_asserter: AsserterFunc | None = None,
    hostname_asserter: AsserterFunc | None = None,
    expected_machine_type: str | None = None,
    expected_min_cpu_platform: str | None = None,
    expected_statuses: list[str] | None = None,
) -> None:
    """Raise an AssertionError if the Instance object does not meet common expectations."""
    if description_asserter is None:
        description_asserter = re_asserter_builder(DEFAULT_INSTANCE_DESCRIPTION_PATTERN)
    if hostname_asserter is None:
        hostname_asserter = re_asserter_builder(DEFAULT_INSTANCE_HOSTNAME_PATTERN)
    if expected_machine_type is None:
        expected_machine_type = DEFAULT_INSTANCE_MACHINE_TYPE
    if expected_statuses is None:
        expected_statuses = [DEFAULT_INSTANCE_EXPECTED_STATUS]
    assert instance is not None
    assert instance.can_ip_forward
    assert not instance.deletion_protection
    description_asserter(instance.description)
    hostname_asserter(instance.hostname)
    assert not instance.key_revocation_action_type
    assert instance.machine_type.endswith(expected_machine_type)
    if expected_min_cpu_platform is not None:
        assert instance.min_cpu_platform == expected_min_cpu_platform
    else:
        assert not instance.min_cpu_platform
    assert not instance.private_ipv6_google_access
    assert not instance.source_machine_image
    assert instance.status in expected_statuses


def default_assert_labels(
    labels: MutableMapping[str, str] | None,
    expected_labels: dict[str, str] | None = None,
) -> None:
    """Raise an AssertionError if the labels do not meet expectations."""
    assert labels is not None
    if expected_labels is not None:
        assert all(item in labels.items() for item in expected_labels.items())


def default_assert_advanced_machine_features(
    features: compute_v1.AdvancedMachineFeatures | None,
) -> None:
    """Raise an AssertionError if the AdvancedMachineFeatures object does not meet expectations."""
    assert features is not None
    assert not features.enable_nested_virtualization
    assert not features.enable_uefi_networking
    assert features.performance_monitoring_unit == ""
    assert features.threads_per_core == 0
    assert features.turbo_mode == ""
    assert features.visible_core_count == 0


def default_assert_confidential_instance_config(
    config: compute_v1.ConfidentialInstanceConfig | None,
) -> None:
    """Raise an AssertionError if the ConfidentialInstanceConfig object does not meet expectations."""
    assert config is not None
    assert not config.enable_confidential_compute
    assert not config.confidential_instance_type


def default_assert_customer_encryption_key(customer_encryption_key: compute_v1.CustomerEncryptionKey | None) -> None:
    """Raise an AssertionError if the CustomerEncryptionKey object does not match expectations."""
    assert customer_encryption_key is not None
    assert not customer_encryption_key.kms_key_name
    assert not customer_encryption_key.kms_key_service_account
    assert not customer_encryption_key.raw_key
    assert not customer_encryption_key.rsa_encrypted_key
    assert not customer_encryption_key.sha256


def default_assert_disks(
    disks: MutableSequence[compute_v1.AttachedDisk],
    disk_size_asserter: AsserterFunc | None = None,
    expected_boot_disk_type: str | None = None,
) -> None:
    """Raise an AssertionError if the Disks sequence of an Instance does not match expectations."""
    if expected_boot_disk_type is None:
        expected_boot_disk_type = DEFAULT_INSTANCE_BOOT_DISK_TYPE
    if disk_size_asserter is None:
        disk_size_asserter = minimum_int_asserter_builder(35)
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
        assert not disk.initialize_params.source_image
        assert disk.interface == "SCSI"
        assert disk.mode == "READ_WRITE"
        assert not disk.saved_state
        assert not disk.shielded_instance_initial_state
        assert disk.source
        assert disk.type_ == "PERSISTENT"


def default_assert_display_device(display_device: compute_v1.DisplayDevice) -> None:
    """Raise an AssertionError if the DisplayDevice object does not match expectations."""
    assert display_device is not None
    assert not display_device.enable_display


def default_assert_accelerator_configs(
    configs: MutableSequence[compute_v1.AcceleratorConfig] | None = None,
) -> None:
    """Raise an AssertionError if the sequence of AcceleratorConfig objects do not match expectations."""
    assert configs is not None
    assert len(configs) == 0


def default_assert_metadata(
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
    cloud_config_asserter(metadata_dict["user-data"])


def default_assert_network_interfaces(
    network_interfaces: MutableSequence[compute_v1.NetworkInterface] | None,
    expected_subnets: list[ipaddress.IPv4Network] | None = None,
) -> None:
    """Raise an AssertionError if the sequence of NetworkInterface objects does not meet expectations."""
    assert network_interfaces is not None
    if expected_subnets is not None:
        assert len(network_interfaces) == len(expected_subnets)
    else:
        assert len(network_interfaces) > 1
    for i, network_interface in enumerate(network_interfaces):
        # NOTE: Most scenarios assign public IP address on eth1 for verification, which is NOT the module default.
        assert len(network_interface.access_configs) == (1 if i == min(len(network_interfaces) - 1, 1) else 0)
        for access_config in network_interface.access_configs:
            public_ip = ipaddress.IPv4Address(access_config.nat_i_p)
            assert public_ip
            assert not public_ip.is_private
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


def default_assert_network_performance_config(
    config: compute_v1.NetworkPerformanceConfig | None,
) -> None:
    """Raise an AssertionError if the NetworkPerformanceConfig object does not meet expectations."""
    assert config is not None
    assert not config.total_egress_bandwidth_tier


def default_assert_reservation_affinity(reservation_affinity: compute_v1.ReservationAffinity | None) -> None:
    """Raise an AssertionError if the ReservationAffinity object does not meet expectations."""
    assert reservation_affinity is not None
    assert not reservation_affinity.consume_reservation_type
    assert not reservation_affinity.key
    assert len(reservation_affinity.values) == 0


def default_assert_resource_manager_tags(
    tags: MutableMapping[str, str] | None,
    expected_tags: dict[str, str] | None = None,
) -> None:
    """Raise an AssertionError if the sequence of resource manager tags does not meet expectations."""
    if expected_tags is None:
        expected_tags = {}
    assert tags is not None
    assert all(item in tags.items() for item in expected_tags.items())


def default_assert_resource_policies(policies: MutableSequence[str] | None) -> None:
    """Raise an AssertionError if the sequence of resource policies does not meet expectations."""
    assert policies is not None
    assert len(policies) == 0


def default_assert_resource_status(status: compute_v1.ResourceStatus | None) -> None:
    """Raise an AssertionError if the ResourceStatus object does not meet expectations."""
    assert status is not None


def default_assert_scheduling(scheduling: compute_v1.Scheduling | None = None) -> None:
    """Raise an AssertionError if the Scheduling object does not meet expectations."""
    assert scheduling is not None
    assert scheduling.automatic_restart
    assert not scheduling.availability_domain
    assert not scheduling.host_error_timeout_seconds
    assert not scheduling.instance_termination_action
    assert not scheduling.local_ssd_recovery_timeout.nanos
    assert not scheduling.local_ssd_recovery_timeout.seconds
    assert not scheduling.max_run_duration.nanos
    assert not scheduling.max_run_duration.seconds
    assert not scheduling.min_node_cpus
    assert len(scheduling.node_affinities) == 0
    assert scheduling.on_host_maintenance == "MIGRATE"
    assert not scheduling.on_instance_stop_action.discard_local_ssd
    assert not scheduling.preemptible
    assert scheduling.provisioning_model == "STANDARD"
    assert not scheduling.skip_guest_os_shutdown
    assert not scheduling.termination_time


def default_assert_service_accounts(
    service_accounts: MutableSequence[compute_v1.ServiceAccount] | None,
    service_account_email_asserter: AsserterFunc | None = None,
) -> None:
    """Raise an AssertionError if the sequence of ServiceAccount objects does not meet expectations."""
    if service_account_email_asserter is None:
        service_account_email_asserter = re_asserter_builder(DEFAULT_INSTANCE_SERVICE_ACCOUNT_EMAIL_PATTERN)
    assert service_accounts is not None
    assert len(service_accounts) == 1
    for service_account in service_accounts:
        service_account_email_asserter(service_account.email)
        assert service_account.scopes == [
            "https://www.googleapis.com/auth/cloud-platform",
        ]


def default_assert_shielded_instance_config(config: compute_v1.ShieldedInstanceConfig | None) -> None:
    """Raise an AssertionError if the ShieldedInstanceConfig object does not meet expectations."""
    assert config is not None
    assert not config.enable_integrity_monitoring
    assert not config.enable_secure_boot
    assert not config.enable_vtpm


def default_assert_shielded_instance_integrity_policy(
    policy: compute_v1.ShieldedInstanceIntegrityPolicy | None,
) -> None:
    """Raise an AssertionError if the ShieldedInstanceIntegrityPolicy object does not meet expectations."""
    assert policy is not None
    assert not policy.update_auto_learn_policy


def default_assert_tags(tags: compute_v1.Tags | None, expected_tags: list[str] | None = None) -> None:
    """Raise an AssertionError if the Tags object does not meet expectations."""
    if expected_tags is None:
        expected_tags = []
    assert tags is not None
    assert tags.items is not None
    assert all(tag in tags.items for tag in expected_tags)


class Scenario:
    """Encapsulates a single BIG-IP version + NIC count stateful test scenario."""

    def __init__(
        self,
        bigip_key: str,
        nic_count: int,
        prefix: str | None = None,
    ) -> None:
        """Initialize a StatefulScenario."""
        if bigip_key not in BIG_IP_IMAGES:
            raise ValueError(f"Unknown BIG-IP key '{bigip_key}'")  # noqa: EM102, TRY003
        if nic_count < 1 or nic_count > 8:  # noqa: PLR2004
            raise ValueError(f"Invalid nic_count value, must be between 1 and 8 inclusive: {nic_count}")  # noqa: EM102, TRY003
        self.bigip_key = bigip_key
        self.nic_count = nic_count
        self.prefix = prefix
        self._tfvars: dict[str, Any] = {}

    def __str__(self) -> str:
        """Return a string for this scenario."""
        return f"{self.prefix}{'-' if self.prefix else ''}{self.bigip_key.replace('.', '-')}-{self.nic_count}n"

    @property
    def tfvars(self) -> dict[str, Any]:
        """Return the tfvars for scenario."""
        interfaces = [
            interface for i, interface in enumerate(self._tfvars.get("interfaces", [])) if i <= self.nic_count
        ]
        return self._tfvars | {
            "prefix": self.__str__(),
            "image": BIG_IP_IMAGES.get(self.bigip_key),
            "interfaces": interfaces,
        }

    @tfvars.setter
    def tfvars(self, value: dict[str, Any]) -> None:
        """Replace tfvars with given value."""
        self._tfvars = value

    @property
    def expected_description(self) -> str:
        """Return a default description for this scenario."""
        return f"{self.nic_count}-nic BIG-IP v{self.bigip_key}"

    @property
    def expected_names(self) -> list[str]:
        """Return a list of expected VM instance names in this scenario."""
        return [
            f"{self!s}-01",
            f"{self!s}-02",
        ]


def scenario_id_builder(scenario: Scenario) -> str:
    """Return a pytest id for the scenario."""
    return f"{scenario.bigip_key}-{scenario.nic_count}n"


def scenario_generator[T](
    scenario_type: type[T],
    versions: set[str] | None = None,
    minimum_nic_count: int | None = None,
    maximum_nic_count: int | None = None,
) -> list[T]:
    """Return a sorted list of Scenarios for the BIG-IP versions and NIC count limits."""
    if versions is None:
        versions = set(BIG_IP_IMAGES)
    if minimum_nic_count is None:
        minimum_nic_count = 2
    if maximum_nic_count is None:
        maximum_nic_count = MAX_NIC_COUNT
    return [
        scenario_type(bigip_key=x[0], nic_count=x[1])
        for x in sorted(
            itertools.product(versions, set(range(minimum_nic_count, maximum_nic_count + 1))),
            key=itemgetter(0, 1),
            reverse=True,
        )
    ]
