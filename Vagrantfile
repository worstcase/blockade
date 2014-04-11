
BOX_NAME = ENV['BOX_NAME'] || "ubuntu"
BOX_URL = ENV['BOX_URL'] || "http://files.vagrantup.com/precise64.box"
VMWARE_BOX_URI = ENV['BOX_URI'] || "http://files.vagrantup.com/precise64_vmware_fusion.box"
script = <<SCRIPT
#!/bin/bash -e

if [ ! -e /vagrant/blockade ]; then
    echo "/vagrant/blockade not found. are we in a vagrant blockade environment??" >&2
    exit 1
fi

if [ ! -f /etc/default/docker ]; then
  echo "/etc/default/docker not found -- is docker installed?" >&2
  exit 1
fi

apt-get -y install lxc python-pip python-virtualenv

if (source /etc/default/docker && [[ $DOCKER_OPTS != *lxc* ]]); then

  echo "Adjusting docker configuration to use LXC driver, and restarting daemon." >&2

  echo '# Blockade requires the LXC driver for now' >> /etc/default/docker
  echo 'DOCKER_OPTS="$DOCKER_OPTS -e lxc"' >> /etc/default/docker
  service docker restart

fi

cd /vagrant

# install into system python
python setup.py install

# and also develop-install into a venv, for dev+test
if [ ! -e /tmp/blockade-ve/bin/activate ]; then
    rm -fr /tmp/blockade-ve
    virtualenv /tmp/blockade-ve
fi
source /tmp/blockade-ve/bin/activate

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
