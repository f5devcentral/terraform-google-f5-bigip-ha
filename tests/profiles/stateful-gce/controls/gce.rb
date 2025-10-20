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

control 'status' do
  title 'Ensure BIG-IP VMs are running'
  impact 1.0
  self_links = input('output_self_links')

  self_links.each_value do |url|
    params = url.match(%r{/projects/(?<project>[^/]+)/zones/(?<zone>[^/]+)/instances/(?<name>.+)$}).named_captures
    describe google_compute_instance(project: params['project'], zone: params['zone'], name: params['name']) do
      it { should exist }
      its('status') { should cmp 'RUNNING' }
    end
  end
end

# rubocop:disable Metrics/BlockLength
control 'configuration' do
  title 'Ensure BIG-IP VM configurations match expectations'
  impact 0.8
  self_links = input('output_self_links')
  prefix = input('output_prefix')
  bigip_sa = input('output_service_account')
  labels = input('output_labels')
  machine_type = input('input_machine_type')
  management = JSON.parse(input('output_mgmt_interface_json', value: '{}'), { symbolize_names: false })
  external = JSON.parse(input('output_external_interface_json', value: '{}'), { symbolize_names: false })
  internals = JSON.parse(input('output_internal_interfaces_json', value: '[]'), { symbolize_names: false }) || []
  instances = JSON.parse(input('output_instances_json', value: '{}'), { symbolize_names: false })

  self_links.each_value do |url|
    params = url.match(%r{/projects/(?<project>[^/]+)/zones/(?<zone>[^/]+)/instances/(?<name>.+)$}).named_captures
    instance = google_compute_instance(project: params['project'], zone: params['zone'], name: params['name'])
    describe instance do
      it { should exist }
      its('name') { should match(/^#{prefix}-\d{2}/) } if instances.nil? || instances.empty?
      its('name') { should be_in instances.keys } unless instances.nil? || instances.empty?
      its('machine_type') { should match %r{/#{machine_type}$} }
      its('disk_count') { should eq 1 }
      its('network_interfaces_count') { should eq 2 + internals.size }
    end

    describe "#{instance} external interface" do
      subject { instance.network_interfaces.first }
      its('subnetwork') { should cmp external['subnet_id'] }
      if external['public_ip']
        its('access_configs.first.nat_ip') { should be_valid_address }
      else
        its('access_configs') { should be_nil }
      end
    end

    describe "#{instance} management interface" do
      subject { instance.network_interfaces[1] }
      its('subnetwork') { should cmp management['subnet_id'] }
      if management['public_ip']
        its('access_configs.first.nat_ip') { should be_valid_address }
      else
        its('access_configs') { should be_nil }
      end
    end

    internals.each_index do |index|
      describe "#{instance} internal interface #{index}" do
        subject { instance.network_interfaces[2 + index] }
        its('subnetwork') { should cmp internals[index]['subnet_id'] }
        if internals[index]['public_ip']
          its('access_configs.first.nat_ip') { should be_valid_address }
        else
          its('access_configs') { should be_nil }
        end
      end
    end

    describe instance.service_accounts.first do
      its('email') { should cmp bigip_sa }
    end

    describe "#{instance} labels" do
      subject { instance.labels }
      if labels.nil? || labels.empty?
        it { should be_nil }
      else
        it { should_not be_nil }
        it { should_not be_empty }
        it { should cmp labels }
      end
    end

    describe "#{instance} metadata" do
      subject { instance.metadata }
      it { should_not be_nil }
      it { should_not be_empty }
    end
    describe "#{instance} metadata bigip_ha_peer_address" do
      subject { instance.metadata_value_by_key('bigip_ha_peer_address') }
      it { should be_valid_address }
    end
    describe "#{instance} metadata bigip_ha_peer_name" do
      subject { instance.metadata_value_by_key('bigip_ha_peer_name') }
      it { should_not be_nil }
      it { should_not be_empty }
    end
    describe "#{instance} metadata bigip_ha_peer_owner_index" do
      subject { instance.metadata_value_by_key('bigip_ha_peer_owner_index') }
      it { should match(/^[01]$/) }
    end
  end
end
# rubocop:enable Metrics/BlockLength
