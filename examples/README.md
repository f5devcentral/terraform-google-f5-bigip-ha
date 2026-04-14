# Examples

The examples are pre-tested with BIG-IP v21.0 and demonstrate how to achieve goals by combining the module(s) with
other Google Cloud resources.

* [stateful-nlb]
  Provisions an active-standby HA pair of BIG-IP VEs with a Google Cloud External Network Load Balancer providing a
  public VIP
* [stateless-nlb]
  Provisions an active-active HA pair of BIG-IP VEs as a Compute Engine Managed Instance Group, with a Google Cloud
  Network Load Balancer providing a public VIP
* [stateful-nlb-byol]
  Also provisions an active-standby HA pair of BIG-IP VEs with NLB, but with static license keys and BYOL image

> If you have a suggestion for an additional example, open a **Feature Request** and we'll look into it.

## Pay-as-you-go (PAYG) vs. Bring-your-own-license (BYOL)

Almost all the examples here use PAYG marketplace images as the source for BIG-IP VE instances. This has the advantage
of allowing the examples to focus on the outcome, not the mechanics around provisioning BIG-IP VEs with valid license
keys. The exception is [stateful-nlb-byol], which deliberately shows one way to assign license keys to individual VE
instances while still using a common deployment script.

> NOTE: We do not recommend beginning your *stateless* deployment journey with static license keys and BYOL images, as
> Google Cloud's Managed Instance Group will create and destroy instances as needed, which can lead to license keys
> being marked as **assigned** despite the instance having been destroyed.

However, if it fits your deployment scenario better, almost every *stateful* example can be converted from PAYG to BYOL
with license keys with a minimum set of changes:

1. Terraform changes
   1. Change the `image` from a PAYG source to a BYOL source
   1. Add license keys to per-instance *metadata* using the `instances` variable

1. Runtime-init configuration changes
   1. Retrieve the license key from instance metadata as a runtime-
   1. Modify the Declarative Onboarding section of `runtime-init-conf.yaml` to use the license key from metadata

For example, the functional changes between [stateful-nlb] and [stateful-nlb-byol] examples is shown below:

<!-- markdownlint-disable -->
```diff
diff -x .git -x '*~' -x '*#' -Naur examples/stateful-nlb/main.tf examples/stateful-nlb-byol/main.tf
--- examples/stateful-nlb/main.tf	2026-04-14 11:13:58.510958009 -0700
+++ examples/stateful-nlb-byol/main.tf	2026-04-14 11:22:05.939837013 -0700
@@ -100,6 +100,19 @@
   source     = "git::https://github.com/f5devcentral/terraform-google-f5-bigip-ha?ref=v0.2.1"
   project_id = var.project_id
   prefix     = var.name
+
+  # Provide per-instance metadata so that a single registration key goes to each BIG-IP VE instance.
+  # NOTE: The instances variable can also be used to override naming, assign Alias IPs as secondary IPs, etc., but for
+  # this example it will stick to the same naming convention and just add license key.
+  instances = { for i in range(0, 2) : format("%s-%02d", var.name, i + 1) => {
+    metadata = {
+      bigip_license_key = var.license_keys[i]
+    }
+  } }
+
+  # Use a bring-your-own-license (BYOL) image; the BIG-IP will be inactive until the license is applied by runtime-init.
+  image = "projects/f5-7626-networks-public/global/images/f5-bigip-21-0-0-1-0-0-13-byol-ltm-1boot-loc-260128094804"
+
   # For consistent and predictable naming, it is important to set the common DNS domain name to use with instances; for
   # example 'your-domain.com'. Instances will be given the host name "{prefix}-0n.{host_domain}".
   # NOTE: BIG-IP hostnames have a limit of 65 characters.
diff -x .git -x '*~' -x '*#' -Naur examples/stateful-nlb/templates/runtime-init-conf.yaml examples/stateful-nlb-byol/templates/runtime-init-conf.yaml
--- examples/stateful-nlb/templates/runtime-init-conf.yaml	2026-04-14 01:26:26.910062013 -0700
+++ examples/stateful-nlb-byol/templates/runtime-init-conf.yaml	2026-04-14 01:26:26.910062013 -0700
@@ -123,6 +123,13 @@
     headers:
       - name: Metadata-Flavor
         value: Google
+  - name: LICENSE_KEY
+    type: url
+    value: http://169.254.169.254/computeMetadata/v1/instance/attributes/bigip_license_key
+    returnType: string
+    headers:
+      - name: Metadata-Flavor
+        value: Google
 pre_onboard_enabled:
   - name: provision_rest
     type: inline
@@ -164,6 +171,10 @@
             timezone: UTC
             servers:
               - 169.254.169.254
+          license:
+            class: License
+            licenseType: regKey
+            regKey: '{{{ LICENSE_KEY }}}'
           admin:
             class: User
             userType: regular
```
<!-- markdownlint-enable -->

[stateful-nlb]: ./stateful-nlb/
[stateful-nlb-byol]: ./stateful-nlb-byol/
[stateless-nlb]: ./stateless-nlb/
