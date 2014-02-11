
BOX_NAME = ENV['BOX_NAME'] || "ubuntu"
BOX_URL = ENV['BOX_URL'] || "http://files.vagrantup.com/precise64.box"
VMWARE_BOX_URI = ENV['BOX_URI'] || "http://files.vagrantup.com/precise64_vmware_fusion.box"
script = <<SCRIPT
#!/bin/bash -e

if [ ! -e /vagrant/blockade ]; then
    echo "/vagrant/blockade not found. are we in a vagrant blockade environment??"
    exit 1
fi

apt-get -y install python-pip python-virtualenv

cd /vagrant

# install into system python
python setup.py install

# and also develop-install into a venv, for dev+test
if [ ! -e /tmp/ve/bin/activate ]; then
    rm -fr /tmp/ve
    virtualenv /tmp/ve
fi
source /tmp/ve/bin/activate

python setup.py develop
pip install blockade[test]

export BLOCKADE_INTEGRATION_TESTS=1
nosetests blockade --with-coverage
SCRIPT

Vagrant.configure("2") do |config|

  config.vm.box = BOX_NAME
  config.vm.box_url = BOX_URL

  config.vm.provider :virtualbox do |vb, override|
  end

  config.vm.provider :vmware_fusion do |vb, override|
    override.vm.box_url = VMWARE_BOX_URI
  end

  config.vm.provision "docker",
    images: ["ubuntu"]

  # kick off the tests automatically
  config.vm.provision "shell", inline: script
end
