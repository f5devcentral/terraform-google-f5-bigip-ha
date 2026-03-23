"""Common testing fixtures that can be added to individual test modules."""

import ipaddress
import os
import pathlib
import re
import shutil
import time
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import google.auth
import pytest
import requests
import requests.auth
from google.api_core import exceptions, extended_operation
from google.cloud import compute_v1, iam_admin_v1, storage

from tests import ADMIN_USER_PASSWORD, DEFAULT_INSTANCE_SELF_LINK_PATTERN, MAX_NIC_COUNT, skip_destroy_phase

DEFAULT_PREFIX = "bigip-ha"
DEFAULT_LABELS = {
    "use_case": "automated-tofu-testing",
    "module": "terraform-google-f5-bigip-ha",
    "driver": "pytest",
}
DEFAULT_REGION = "us-central1"
DEFAULT_TF_STATE_PREFIX = "tests/terraform-google-f5-bigip-ha"
DEFAULT_ADMIN_USER = "admin"
DEFAULT_WAIT_FOR_TIMEOUT = timedelta(seconds=1200)


@pytest.fixture(scope="session")
def subnet_ranges_builder() -> Callable[[int | None], list[ipaddress.IPv4Network]]:
    """Return a builder that will return range of CIDRs to use for test scenario subnets."""
    ranges = list(ipaddress.IPv4Network("172.16.0.0/12").subnets(new_prefix=24))[:8]

    def _builder(count: int | None = None) -> list[ipaddress.IPv4Network]:
        if count is None:
            count = MAX_NIC_COUNT
        assert count >= 1
        assert count <= len(ranges)
        return ranges[:count]

    return _builder


@pytest.fixture(scope="session")
def prefix() -> str:
    """Return the prefix to use for test resources.

    Preference will be given to the environment variable TEST_PREFIX with default value of 'bigip-ha'.
    """
    prefix = os.getenv("TEST_PREFIX", DEFAULT_PREFIX)
    if prefix:
        prefix = prefix.strip()
    if not prefix:
        prefix = DEFAULT_PREFIX
    assert prefix
    return prefix


@pytest.fixture(scope="session")
def project_id() -> str:
    """Return the project id to use for tests.

    Preference will be given to the environment variables TEST_GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_PROJECT followed by
    the default project identifier associated with local ADC credentials.
    """
    project_id = os.getenv("TEST_GOOGLE_CLOUD_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT")
    if project_id:
        project_id = project_id.strip()
    if not project_id:
        _, project_id = google.auth.default()
    assert project_id
    return project_id


@pytest.fixture(scope="session")
def labels() -> dict[str, str]:
    """Return a dict of labels to apply to resources from environment variable TEST_GOOGLE_LABELS.

    If the environment variable TEST_GOOGLE_LABELS is not empty and can be parsed as a comma-separated list of key:value
    pairs then return a dict of keys to values.
    """
    raw = os.getenv("TEST_GOOGLE_LABELS")
    if not raw:
        return DEFAULT_LABELS
    return DEFAULT_LABELS | dict([x.split(":") for x in raw.split(",")])


@pytest.fixture(scope="session")
def region() -> str:
    """Return the Compute Engine region to use for tests.

    Preference will be given to the environment variable TEST_GOOGLE_REGION with fallback to the default value of
    'us-central1'.
    """
    region = os.getenv("TEST_GOOGLE_REGION", DEFAULT_REGION)
    if region:
        region = region.strip()
    if not region:
        region = DEFAULT_REGION
    assert region
    return region


@pytest.fixture(scope="session")
def tf_state_bucket() -> str:
    """Return the Google Cloud Storage bucket name to use for tofu/terraform state files."""
    bucket = os.getenv("TEST_GOOGLE_TF_STATE_BUCKET")
    if bucket:
        bucket = bucket.strip()
    assert bucket
    return bucket


@pytest.fixture(scope="session")
def tf_state_prefix() -> str:
    """Return the prefix to use for tofu/terraform state files in bucket.

    Preference will be given to the variable TEST_GOOGLE_TF_STATE_PREFIX with fallback to the default value of
    'tests/terraform-google-f5-bigip-ha'.
    """
    prefix = os.getenv("TEST_GOOGLE_TF_STATE_PREFIX", DEFAULT_TF_STATE_PREFIX)
    if prefix:
        prefix = prefix.strip()
    if not prefix:
        prefix = DEFAULT_TF_STATE_PREFIX
    assert prefix
    return prefix


@pytest.fixture(scope="session")
def backend_tf_builder(tf_state_bucket: str, tf_state_prefix: str) -> Callable[[pathlib.Path, str], None]:
    """Create or overwrite a _backend.tf file in the provided fixture_dir that configures GCS backend for state."""

    def _backend_tf(fixture_dir: pathlib.Path, name: str) -> None:
        assert fixture_dir.exists()
        assert name
        fixture_dir.joinpath("_backend.tf").write_text(
            "\n".join(
                [
                    "terraform {",
                    '  backend "gcs" {',
                    f'    bucket = "{tf_state_bucket}"',
                    f'    prefix = "{tf_state_prefix}/{name}"',
                    "  }",
                    "}",
                ],
            ),
        )

    return _backend_tf


@pytest.fixture(scope="session")
def common_fixture_dir_ignores() -> Callable[[Any, list[str]], set[str]]:
    """Return a set of ignore patterns that are unrelated to module sources or supporting files."""
    return shutil.ignore_patterns(".*", "*.md", "*.toml", "uv.lock", "tests")


@pytest.fixture(scope="session")
def root_module_dir() -> pathlib.Path:
    """Return the Path of the root module."""
    root_module_dir = pathlib.Path(__file__).parent.parent.resolve()
    assert root_module_dir.exists()
    assert root_module_dir.is_dir()
    assert root_module_dir.joinpath("main.tf").exists()
    assert root_module_dir.joinpath("outputs.tf").exists()
    assert root_module_dir.joinpath("variables.tf").exists()
    return root_module_dir


@pytest.fixture(scope="session")
def fixture_dir(
    tmp_path_factory: pytest.TempPathFactory,
    backend_tf_builder: Callable[..., None],
    common_fixture_dir_ignores: Callable[[Any, list[str]], set[str]],
    root_module_dir: pathlib.Path,
) -> Callable[[str], pathlib.Path]:
    """Return a builder that makes a copy of the root module with backend configured appropriately."""

    def _builder(name: str) -> pathlib.Path:
        fixture_dir = tmp_path_factory.mktemp(name)
        shutil.copytree(
            src=root_module_dir,
            dst=fixture_dir,
            dirs_exist_ok=True,
            ignore=common_fixture_dir_ignores,
        )
        backend_tf_builder(
            fixture_dir=fixture_dir,
            name=name,
        )
        return fixture_dir

    return _builder


@pytest.fixture(scope="session")
def template_module_dir() -> pathlib.Path:
    """Return the Path of the template module."""
    module_dir = pathlib.Path(__file__).parent.parent.joinpath("modules/template").resolve()
    assert module_dir.exists()
    assert module_dir.is_dir()
    assert module_dir.joinpath("main.tf").exists()
    assert module_dir.joinpath("outputs.tf").exists()
    assert module_dir.joinpath("variables.tf").exists()
    return module_dir


@pytest.fixture(scope="session")
def template_fixture_dir(
    tmp_path_factory: pytest.TempPathFactory,
    backend_tf_builder: Callable[..., None],
    common_fixture_dir_ignores: Callable[[Any, list[str]], set[str]],
    template_module_dir: pathlib.Path,
) -> Callable[[str], pathlib.Path]:
    """Return a builder that makes a copy of the template sub-module source with backend configured appropriately."""

    def _builder(name: str) -> pathlib.Path:
        fixture_dir = tmp_path_factory.mktemp(name)
        shutil.copytree(
            src=template_module_dir,
            dst=fixture_dir,
            dirs_exist_ok=True,
            ignore=common_fixture_dir_ignores,
        )
        backend_tf_builder(
            fixture_dir=fixture_dir,
            name=name,
        )
        return fixture_dir

    return _builder


@pytest.fixture(scope="session")
def instances_client() -> compute_v1.InstancesClient:
    """Return a reusable Compute Engine v1 Instances API client."""
    return compute_v1.InstancesClient()


@pytest.fixture(scope="session")
def instances_builder(instances_client: compute_v1.InstancesClient) -> Callable[[list[str]], list[compute_v1.Instance]]:
    """Return a Instances list builder that takes a list of self-link strings."""

    def _builder(self_links: list[str] | None) -> list[compute_v1.Instance]:
        assert self_links is not None
        instances: list[compute_v1.Instance] = []
        for match in [re.search(DEFAULT_INSTANCE_SELF_LINK_PATTERN, self_link) for self_link in self_links]:
            assert match
            project, zone, name = match.groups()
            instances.append(
                instances_client.get(
                    request=compute_v1.GetInstanceRequest(
                        project=project,
                        zone=zone,
                        instance=name,
                    ),
                ),
            )
        return instances

    return _builder


def get_public_address(instance: compute_v1.Instance, interface_index: int | None = None) -> str:
    """Extract the public IP address of the instance's interface at index."""
    assert instance.network_interfaces
    if interface_index is None:
        # Default to expected management interface
        interface_index = min(len(instance.network_interfaces) - 1, 1)
    interface = instance.network_interfaces[interface_index]
    assert interface
    assert interface.access_configs
    assert interface.access_configs[0]
    assert interface.access_configs[0].nat_i_p
    return interface.access_configs[0].nat_i_p


def management_url(instance: compute_v1.Instance) -> str:
    """Return the base management HTTPS URL for Compute Engine instance."""
    return f"https://{get_public_address(instance=instance)}{':8443' if len(instance.network_interfaces) == 1 else ''}"


@pytest.fixture(scope="session")
def admin_basic_auth() -> requests.auth.HTTPBasicAuth:
    """Return a reusable HTTPBasicAuth object for management interface authentication."""
    return requests.auth.HTTPBasicAuth(username="admin", password=ADMIN_USER_PASSWORD)


@pytest.fixture(scope="session")
def sys_ready_retriever(
    admin_basic_auth: requests.auth.HTTPBasicAuth,
) -> Callable[[compute_v1.Instance], dict[str, Any]]:
    """Return a retriever and parser for iControlRest /mgmt/tm/sys/ready endpoint."""

    def _retriever(instance: compute_v1.Instance) -> dict[str, Any]:
        return requests.get(
            url=f"{management_url(instance)}/mgmt/tm/sys/ready",
            auth=admin_basic_auth,
            verify=False,
        ).json()

    return _retriever


@pytest.fixture(scope="session")
def cm_device_retriever(
    admin_basic_auth: requests.auth.HTTPBasicAuth,
) -> Callable[[compute_v1.Instance], dict[str, Any]]:
    """Return a retriever and parser for iControlRest /mgmt/tm/cm/device endpoints."""

    def _retriever(instance: compute_v1.Instance) -> dict[str, Any]:
        return requests.get(
            url=f"{management_url(instance)}/mgmt/tm/cm/device/{instance.hostname}",
            auth=admin_basic_auth,
            verify=False,
        ).json()

    return _retriever


@pytest.fixture(scope="session")
def active_standby_asserter(
    cm_device_retriever: Callable[[compute_v1.Instance], dict[str, Any]],
) -> Callable[[list[compute_v1.Instance]], None]:
    """Return an asserter function that verifies one instance is 'active', and all others are 'standby'."""

    def _asserter(instances: list[compute_v1.Instance]) -> None:
        states = Counter([cm_device_retriever(instance).get("failoverState", "unknown") for instance in instances])
        assert states["active"] == 1
        assert states["standby"] == len(instances) - 1
        assert not states["unknown"]

    return _asserter


@pytest.fixture(scope="session")
def bigip_is_ready_asserter(
    sys_ready_retriever: Callable[[compute_v1.Instance], dict[str, Any]],
) -> Callable[[compute_v1.Instance], None]:
    """Return an asserter function that verifies a BIG-IP instance is ready for use."""

    def _asserter(instance: compute_v1.Instance) -> None:
        result = sys_ready_retriever(instance)
        assert result
        entries = (
            result.get("entries", {})
            .get("https://localhost/mgmt/tm/sys/ready/0", {})
            .get("nestedStats", {})
            .get("entries", {})
        )
        assert entries
        assert entries.get("configReady", {}).get("description", "no") == "yes"
        assert entries.get("licenseReady", {}).get("description", "no") == "yes"
        assert entries.get("provisionReady", {}).get("description", "no") == "yes"

    return _asserter


@pytest.fixture(scope="session")
def wait_for_onboarding_complete(
    project_id: str,
    instances_client: compute_v1.InstancesClient,
) -> Callable[[compute_v1.Instance, timedelta | None], compute_v1.Instance]:
    """Return a function that will wait until the instance has been running for the duration provided."""

    def _onboarding_complete(instance: compute_v1.Instance) -> bool:
        """Return True if the instance's guest-attribute 'f5-big-ip/onboarding' is 'complete'."""
        try:
            response = instances_client.get_guest_attributes(
                request=compute_v1.GetGuestAttributesInstanceRequest(
                    instance=instance.name,
                    project=project_id,
                    zone=instance.zone.split("/")[-1],
                    variable_key="f5-big-ip/onboarding",
                ),
            )
        except exceptions.NotFound:
            return False

        return response.variable_value == "complete"

    def _wait(instance: compute_v1.Instance, timeout: timedelta | None = None) -> compute_v1.Instance:
        timeout_ts = datetime.now(UTC) + (timeout if timeout is not None else DEFAULT_WAIT_FOR_TIMEOUT)
        while not _onboarding_complete(instance):
            if datetime.now(UTC) > timeout_ts:
                raise TimeoutError
            time.sleep(10)
        return instances_client.get(
            request=compute_v1.GetInstanceRequest(
                instance=instance.name,
                project=project_id,
                zone=instance.zone.split("/")[-1],
            ),
        )

    return _wait


@pytest.fixture(scope="session")
def guest_attributes_asserter(
    project_id: str,
    instances_client: compute_v1.InstancesClient,
) -> Callable[[compute_v1.Instance, dict[str, str] | None], None]:
    """Return an asserter of instance guest attributes."""

    def _asserter(instance: compute_v1.Instance, expected_attributes: dict[str, str] | None = None) -> None:
        if expected_attributes is None:
            expected_attributes = {
                "mgmt-iface": "complete",
                "onboarding": "complete",
                "runtime-init-checksum": "complete",
                "runtime-init-download": "complete",
                "runtime-init-execution": "complete",
                "runtime-init-install": "complete",
                "set-db": "complete",
            }
            if len(instance.network_interfaces) <= 1:
                del expected_attributes["mgmt-iface"]
        assert instance
        try:
            attributes = instances_client.get_guest_attributes(
                request=compute_v1.GetGuestAttributesInstanceRequest(
                    instance=instance.name,
                    project=project_id,
                    zone=instance.zone.split("/")[-1],
                    query_path="f5-big-ip/",
                ),
            )
            assert attributes
            assert attributes.query_value
            attributes_dict = {entry.key: entry.value for entry in attributes.query_value.items}
            assert all(item in attributes_dict.items() for item in expected_attributes.items())
        except exceptions.NotFound:
            raise AssertionError from None

    return _asserter


@pytest.fixture(scope="session")
def instance_templates_client() -> compute_v1.InstanceTemplatesClient:
    """Return a reusable Compute Engine v1 Instance Templates API client."""
    return compute_v1.InstanceTemplatesClient()


@pytest.fixture(scope="session")
def networks_client() -> compute_v1.NetworksClient:
    """Return an initialized Compute Engine v1 Networks API client."""
    return compute_v1.NetworksClient()


@pytest.fixture(scope="session")
def subnetworks_client() -> compute_v1.SubnetworksClient:
    """Return an initialized Compute Engine v1 Subnetworks API client."""
    return compute_v1.SubnetworksClient()


def handle_extended_operation(operation: extended_operation.ExtendedOperation, timeout: int = 300) -> Any:  # noqa: ANN401
    """Watch the operation and raise an error if it indicates a failure."""
    result = operation.result(timeout=timeout)
    if operation.error_code:
        raise operation.exception() or RuntimeError(operation.error_message)
    return result


@pytest.fixture(scope="session")
def network_builder(
    request: pytest.FixtureRequest,
    project_id: str,
    networks_client: compute_v1.NetworksClient,
) -> Callable[[str, str], str]:
    """Return a builder of global VPC networks."""

    def _builder(name: str, description: str | None = None) -> str:
        """Create a VPC network with given name, returning it's self-link, with automatic deletion after use."""
        assert name
        if description is None:
            description = "VPC network for automated BIG-IP HA repo testing."

        def _cleanup() -> None:
            if not skip_destroy_phase():
                handle_extended_operation(
                    networks_client.delete(
                        request=compute_v1.DeleteNetworkRequest(
                            network=name,
                            project=project_id,
                        ),
                    ),
                )

        try:
            network = networks_client.get(
                request=compute_v1.GetNetworkRequest(
                    network=name,
                    project=project_id,
                ),
            )
            self_link = network.self_link
        except exceptions.NotFound:
            handle_extended_operation(
                networks_client.insert(
                    request=compute_v1.InsertNetworkRequest(
                        network_resource=compute_v1.Network(
                            name=name,
                            auto_create_subnetworks=False,
                            description=description,
                        ),
                        project=project_id,
                    ),
                ),
            )
            self_link = f"https://www.googleapis.com/compute/v1/projects/{project_id}/global/networks/{name}"

        request.addfinalizer(_cleanup)
        return self_link

    return _builder


@pytest.fixture(scope="session")
def subnet_builder(
    request: pytest.FixtureRequest,
    project_id: str,
    region: str,
    subnetworks_client: compute_v1.SubnetworksClient,
) -> Callable[[str, str, str], str]:
    """Return a builder of subnets."""

    def _builder(
        name: str,
        cidr: str,
        network_self_link: str,
        description: str | None = None,
    ) -> str:
        """Create a VPC subnetwork with given name, returning it's self-link, with automatic deletion after use."""
        assert name
        assert cidr
        assert network_self_link
        if description is None:
            description = "VPC subnet for automated BIG-IP HA repo testing."

        def _cleanup() -> None:
            if not skip_destroy_phase():
                handle_extended_operation(
                    subnetworks_client.delete(
                        request=compute_v1.DeleteSubnetworkRequest(
                            subnetwork=name,
                            project=project_id,
                            region=region,
                        ),
                    ),
                )

        try:
            subnet = subnetworks_client.get(
                request=compute_v1.GetSubnetworkRequest(
                    subnetwork=name,
                    project=project_id,
                    region=region,
                ),
            )
            self_link = subnet.self_link
        except exceptions.NotFound:
            handle_extended_operation(
                subnetworks_client.insert(
                    request=compute_v1.InsertSubnetworkRequest(
                        subnetwork_resource=compute_v1.Subnetwork(
                            name=name,
                            description=description,
                            network=network_self_link,
                            ip_cidr_range=cidr,
                            region=region,
                        ),
                        project=project_id,
                        region=region,
                    ),
                ),
            )
            self_link = (
                f"https://www.googleapis.com/compute/v1/projects/{project_id}/regions/{region}/subnetworks/{name}"
            )

        request.addfinalizer(_cleanup)
        return self_link

    return _builder


@pytest.fixture(scope="session")
def iam_admin_client() -> iam_admin_v1.IAMClient:
    """Return an initialized IAM Admin v1 client."""
    return iam_admin_v1.IAMClient()


@pytest.fixture(scope="session")
def service_account_builder(
    request: pytest.FixtureRequest,
    project_id: str,
    iam_admin_client: iam_admin_v1.IAMClient,
) -> Callable[[str, str, str], str]:
    """Return a builder of service accounts."""

    def _builder(
        name: str,
        display_name: str | None = None,
        description: str | None = None,
    ) -> str:
        """Create a service account with given name, returning it's email address, with automatic deletion after use."""
        if display_name is None:
            display_name = "terraform-google-f5-bigip-ha test account"
        if description is None:
            description = "A test service account for automated BIG-IP HA repo testing."

        def _cleanup() -> None:
            if not skip_destroy_phase():
                iam_admin_client.delete_service_account(
                    request=iam_admin_v1.DeleteServiceAccountRequest(
                        name=sa.name,
                    ),
                )

        try:
            sa_accounts = iam_admin_client.list_service_accounts(
                name=f"projects/{project_id}",
            )
            sa = next(sa for sa in sa_accounts if re.search(f"serviceAccounts/{name}", sa.name))
        except (StopIteration, exceptions.NotFound):
            sa = iam_admin_client.create_service_account(
                request=iam_admin_v1.CreateServiceAccountRequest(
                    account_id=name,
                    name=f"projects/{project_id}",
                    service_account=iam_admin_v1.ServiceAccount(
                        display_name=display_name,
                        description=description,
                    ),
                ),
            )
        request.addfinalizer(_cleanup)
        return sa.email

    return _builder


@pytest.fixture(scope="session")
def region_instance_group_managers_client() -> compute_v1.RegionInstanceGroupManagersClient:
    """Return a reusable Compute Engine v1 Regional Instance Group Managers Client API client."""
    return compute_v1.RegionInstanceGroupManagersClient()


@pytest.fixture(scope="session")
def region_instance_groups_client() -> compute_v1.RegionInstanceGroupsClient:
    """Return a reusable Compute Engine v1 Instance Groups Client API client."""
    return compute_v1.RegionInstanceGroupsClient()


@pytest.fixture(scope="session")
def firewalls_client() -> compute_v1.FirewallsClient:
    """Return a reusable Compute Engine v1 Firewalls Client API client."""
    return compute_v1.FirewallsClient()


@pytest.fixture(scope="session")
def source_cidr() -> str:
    """Return the public IPv4 address of this testing machine, as reported by AWS, to use as testing source CIDR."""
    ip_address = requests.get("https://checkip.amazonaws.com").text.strip()
    assert ip_address
    return f"{ip_address}/32"


@pytest.fixture(scope="session")
def allow_ingress_firewall_builder(
    request: pytest.FixtureRequest,
    project_id: str,
    firewalls_client: compute_v1.FirewallsClient,
    source_cidr: str,
) -> Callable[[str, str], str]:
    """Return a builder of VPC network firewalls that allow ingress to everything from the source address."""

    def _builder(network: str, name: str) -> str:
        """Create a Firewall Rule on the network."""

        def _cleanup() -> None:
            if not skip_destroy_phase():
                firewalls_client.delete(
                    request=compute_v1.DeleteFirewallRequest(
                        firewall=name,
                        project=project_id,
                    ),
                )

        try:
            rule = firewalls_client.get(
                request=compute_v1.GetFirewallRequest(
                    firewall=name,
                    project=project_id,
                ),
            )
        except exceptions.NotFound:
            rule = firewalls_client.insert(
                request=compute_v1.InsertFirewallRequest(
                    firewall_resource=compute_v1.Firewall(
                        name=name,
                        description="Allow ingress from testing workstation",
                        direction="INGRESS",
                        priority=500,
                        network=network,
                        allowed=[
                            compute_v1.Allowed(
                                I_p_protocol="all",
                            ),
                        ],
                        source_ranges=[
                            source_cidr,
                        ],
                    ),
                    project=project_id,
                ),
            )
        request.addfinalizer(_cleanup)
        return rule.self_link

    return _builder


@pytest.fixture(scope="session")
def runtime_init_conf() -> str:
    """Return a runtime-init configuration YAML as string."""
    runtime_init_conf = pathlib.Path(__file__).parent.joinpath("files/runtime-init-conf.yaml").resolve()
    assert runtime_init_conf.exists()
    assert runtime_init_conf.is_file()
    return runtime_init_conf.read_text()


@pytest.fixture(scope="session")
def storage_client() -> storage.Client:
    """Return an initialized Storage v1 API client."""
    return storage.Client()


@pytest.fixture(scope="session")
def bucket_builder(
    request: pytest.FixtureRequest,
    pytestconfig: pytest.Config,
    project_id: str,
    storage_client: storage.Client,
) -> Callable[[str], str]:
    """Return a builder of GCS buckets."""

    def _builder(prefix: str, readers: list[str] | None = None, writers: list[str] | None = None) -> str:
        """Create a storage bucket with given prefix, returning it's name, with automatic deletion after use."""
        assert prefix
        cache_key = f"terraform-google-f5-bigip-ha/bucket-{prefix}"
        name = pytestconfig.cache.get(cache_key, None)
        if name is None:
            name = f"{prefix}-{os.urandom(2).hex()}"
            pytestconfig.cache.set(cache_key, name)

        def _cleanup() -> None:
            if not skip_destroy_phase():
                try:
                    bucket = storage_client.get_bucket(
                        bucket_or_name=name,
                    )
                    bucket.delete(force=True)
                    pytestconfig.cache.set(cache_key, None)
                except exceptions.NotFound:
                    pytestconfig.cache.set(cache_key, None)

        try:
            bucket = storage_client.get_bucket(
                bucket_or_name=name,
            )
        except exceptions.NotFound:
            bucket = storage_client.create_bucket(
                bucket_or_name=name,
                user_project=project_id,
                project=project_id,
            )
            bucket.iam_configuration.uniform_bucket_level_access_enabled = True
        assert bucket
        if readers or writers:
            policy = bucket.get_iam_policy()
            if readers:
                policy.bindings.append({"role": "roles/storage.objectViewer", "members": readers})
            if writers:
                policy.bindings.append({"role": "roles/storage.objectAdmin", "members": writers})
            bucket.set_iam_policy(policy)
        request.addfinalizer(_cleanup)
        assert bucket.name
        return bucket.name

    return _builder
