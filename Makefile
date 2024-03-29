# This makefile implements wrappers around various kitchen test commands. The
# intent is to make it easy to execute a full test suite, or individual actions,
# with a safety net that ensures the test harness is present before executing
# kitchen commands. Specifically, Terraform in /test/setup/ has been applied, and
# the examples have been cloned to an emphemeral folder and source modified to
# use these local files.
#
# Every kitchen command has an equivalent target; kitchen action [pattern] becomes
# make action[.pattern]
#
# E.g.
#   kitchen test                 =>   make test
#   kitchen verify example-gsr   =>   make verify.example-gsr
#   kitchen converge pr          =>   make converge.pr
#
# Default target will create necessary test harness, then launch kitchen test.
.DEFAULT: test
.PHONY: test.%
test.%: test/setup/harness.tfvars
	kitchen test $*

.PHONY: test
test: test/setup/harness.tfvars
	kitchen test

.PHONY: destroy.%
destroy.%: test/setup/harness.tfvars
	kitchen destroy $*

.PHONY: destroy
destroy: test/setup/harness.tfvars
	kitchen destroy

.PHONY: verify.%
verify.%: test/setup/harness.tfvars
	kitchen verify $*

.PHONY: verify
verify: test/setup/harness.tfvars
	kitchen verify

.PHONY: converge.%
converge.%: test/setup/harness.tfvars
	kitchen converge $*

.PHONY: converge
converge: test/setup/harness.tfvars
	kitchen converge

EXAMPLES=ha-via-api ha-via-lb sandwich

test/setup/harness.tfvars: $(wildcard test/setup/*.tf) $(wildcard test/setup/*.auto.tfvars) $(wildcard test/setup/terraform.tfvars) $(addprefix test/ephemeral/,$(addsuffix /main.tf,$(EXAMPLES)))
	terraform -chdir=test/setup init -input=false
	terraform -chdir=test/setup apply -input=false -auto-approve -target random_pet.prefix -target random_password.random_password
	terraform -chdir=test/setup apply -input=false -auto-approve

# We want the examples to use the registry tagged versions of the module, but
# need to test against the local code. Make an ephemeral copy of each example
# with the source redirected to local module
test/ephemeral/%/main.tf: $(wildcard examples/%/*.tf)
	mkdir -p $(@D)
	rsync -avP --exclude .terraform \
		--exclude .terraform.lock.hcl \
		--exclude 'terraform.tfstate' \
		examples/$*/ $(@D)/
	sed -i '' -E -e '1h;2,$$H;$$!d;g' -e 's@module "ha"[ \t]*{[ \t]*\n[ \t]*source[ \t]*=[ \t]*"[^"]+"@module "ha" {\n  source = "../../../"@' $@
	sed -i '' -E -e '1h;2,$$H;$$!d;g' -e 's@module "(ilb|nlb|forwarding-rule)"[ \t]*{[ \t]*\n[ \t]*source[ \t]*=[ \t]*"[^"]+"@module "\1" {\n  source = "../../../modules/\1/"@g' $@

.PHONY: clean
clean: $(wildcard test/setup/harness.tfvars)
	-if test -n "$<" && test -f "$<"; then kitchen destroy; fi
	if test -n "$<" && test -f "$<"; then terraform -chdir=$(<D) destroy -auto-approve; fi

.PHONY: realclean
realclean: clean
	find test/reports -depth 1 -type d -exec rm -rf {} +
	find test/ephemeral -depth 1 -type d -exec rm -rf {} +
	find . -type d -name .terraform -exec rm -rf {} +
	find . -type d -name terraform.tfstate.d -exec rm -rf {} +
	find . -type f -name .terraform.lock.hcl -exec rm -f {} +
	find . -type f -name terraform.tfstate -exec rm -f {} +
	find . -type f -name terraform.tfstate.backup -exec rm -f {} +
	rm -rf .kitchen

# Helper to ensure code is ready for tagging
# 1. Tag is a valid semver with v prefix (e.g. v1.0.0)
# 1. Git tree is clean
# 2. Each module is using a f5devcentral GitHub source and the version matches
#    the tag to be applied
# 3. CHANGELOG has an entry for the tag
# 4. Inspec controls have version matching the tag
# if all those pass, tag HEAD with version
.PHONY: tag.%
tag.%:
	@echo '$*' | grep -Eq '^v(?:[0-9]+\.){2}[0-9]+$$' || \
		(echo "Tag doesn't meet requirements"; exit 1)
	@test "$(shell git status --porcelain | wc -l | grep -Eo '[0-9]+')" == "0" || \
		(echo "Git tree is unclean"; exit 1)
	@find examples -type f -name main.tf -print0 | \
		xargs -0 awk 'BEGIN{m=0;s=0}; /module "ha"/ {m=1}; m==1 && /source[ \t]*=[ \t]*"(https:\/\/)?github.com\/f5devcentral\/terraform-google-f5-bigip-ha\?ref=$*/ {s++}; END{if (s==0) { printf "%s has incorrect ha source\n", FILENAME; exit 1}}'
	@find examples -type f -name main.tf -print0 | \
		xargs -0 awk 'BEGIN{m=0;s=0}; /module "(ilb|nlb|forwarding-rule)"/ {m=1}; m==1 && /source[ \t]*=[ \t]*"(https:\/\/)?github.com\/f5devcentral\/terraform-google-f5-bigip-ha\/\/modules\/(ilb|nlb|forwarding-rule)\?ref=$*"/ {s++}; END{if (s==0) { printf "%s has incorrect ilb/nlb/forwarding-rule source\n", FILENAME; exit 1 }}'
	@(grep -Eq '^## \[$(subst .,\.,$(*:v%=%))\] - [0-9]{4}(?:-[0-9]{2}){2}' CHANGELOG.md && \
		grep -Eq '^\[$(subst .,\.,$(*:v%=%))\]: https://github.com/' CHANGELOG.md) || \
		(echo "CHANGELOG is missing tag entry"; exit 1)
	@grep -Eq '^version:[ \t]*$(subst .,\.,$(*:v%=%))[ \t]*$$' test/profiles/ha-gce/inspec.yml || \
		(echo "test/profiles/ha-gce/inspec.yml has incorrect tag"; exit 1)
	@grep -Eq '^version:[ \t]*$(subst .,\.,$(*:v%=%))[ \t]*$$' test/profiles/ha-ssh/inspec.yml || \
		(echo "test/profiles/ha-ssh/inspec.yml has incorrect tag"; exit 1)
	git tag -am 'Tagging release $*' $*
