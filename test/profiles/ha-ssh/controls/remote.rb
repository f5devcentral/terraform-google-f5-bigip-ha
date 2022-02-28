# frozen_string_literal: true

control 'os' do
  title 'Verify BIG-IP reported operating system'
  impact 0.8
  describe os.name do
    it { should eq 'centos' }
  end
end
