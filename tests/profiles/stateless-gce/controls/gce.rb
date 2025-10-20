# frozen_string_literal: true

require 'ipaddr'
require 'json'
require 'time'
require 'rspec/expectations'

RSpec::Matchers.define :be_valid_address do
  match do |address|
    ip = IPAddr.new(address)
    ip.ipv4? || ip.ipv6?
  rescue IPAddr::AddressFamilyError
    false
  end
end

control 'mig' do
  title 'Ensure BIG-IP MIG meets expectations'
  impact 1.0
  self_link = input('output_instance_group_manager')
  prefix = input('output_prefix')
  num_instances = input('input_num_instances').to_i || 2

  # rubocop:disable Layout/LineLength
  params = self_link.match(%r{/projects/(?<project>[^/]+)/regions/(?<region>[^/]+)/instanceGroupManagers/(?<name>.+)$}).named_captures
  # rubocop:enable Layout/LineLength
  describe google_compute_region_instance_group_manager(project: params['project'], region: params['region'],
                                                        name: params['name']) do
    it { should exist }
    its('base_instance_name') { should cmp prefix }
    its('target_size') { should eq num_instances }
  end
end

control 'template' do
  title 'Ensure BIG-IP VM configurations match expectations'
  impact 0.8
  project = input('output_project_id')
  prefix = input('output_prefix')
  bigip_sa = input('output_service_account')
  machine_type = input('input_machine_type')
  internals = JSON.parse(input('output_internal_interfaces_json', value: '[]'), { symbolize_names: false }) || []

  describe google_compute_instance_templates(project:).where(name: /^#{prefix}/) do
    its('count') { should eq 1 }
    its('properties.first.machine_type') { should match %r{/?#{machine_type}$} }
    its('properties.first.disks.count') { should eq 1 }
    its('properties.first.network_interfaces.count') { should eq 2 + internals.size }
    its('properties.first.service_accounts.first.email') { should eq bigip_sa }
  end
end
