# frozen_string_literal: true

control 'os' do
  title 'Verify SSH access to BIG-IP'
  impact 0.8
  describe os.name do
    it { should eq 'centos' }
  end
end
