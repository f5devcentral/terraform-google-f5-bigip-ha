# frozen_string_literal: true

require 'time'

ONBOARDING_SECS = 360

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
  zones = input('output_zones')
  bigip_sa = input('output_bigip_sa')
  labels = input('output_labels')
  machine_type = input('input_machine_type')
  num_nics = input('input_num_nics').to_i

  self_links.each_value do |url|
    params = url.match(%r{/projects/(?<project>[^/]+)/zones/(?<zone>[^/]+)/instances/(?<name>.+)$}).named_captures
    instance = google_compute_instance(project: params['project'], zone: params['zone'], name: params['name'])
    describe instance do
      it { should exist }
      its('name') { should match /#{prefix}-\h{4}/ }
      its('machine_type') { should match %r{/#{machine_type}$} }
      its('disk_count') { should eq 1 }
      its('network_interfaces_count') { should eq num_nics }
    end
    describe instance.zone.split('/').last do
      it { should be_in zones }
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
  end
end
# rubocop:enable Metrics/BlockLength

control 'ready' do
  title 'Ensure BIG-IP VMs have been running long enough to verify onboarding'
  impact 1.0
  self_links = input('output_self_links')

  self_links.each_value do |url|
    params = url.match(%r{/projects/(?<project>[^/]+)/zones/(?<zone>[^/]+)/instances/(?<name>.+)$}).named_captures
    instance = google_compute_instance(project: params['project'], zone: params['zone'], name: params['name'])
    describe instance do
      it "has been running for >= #{ONBOARDING_SECS} seconds" do
        expect(Time.iso8601(instance.creation_timestamp)).to be <= (Time.now - ONBOARDING_SECS)
      end
    end
  end
end
