
VAGRANTFILE_API_VERSION = "2"
BOX_NAME = ENV['BOX_NAME'] || "ubuntu/trusty64"
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

apt-get update
apt-get -y install python-pip python-virtualenv

cd /vagrant

export PIP_DOWNLOAD_CACHE=/vagrant/.pip_download_cache

# install into system python for manual testing
python setup.py develop

# apt version of tox is still too old in trusty
pip install tox

tox
SCRIPT

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|

  config.vm.box = BOX_NAME

  if Vagrant.has_plugin?("vagrant-cachier")
    config.cache.scope = :box
  end

  config.vm.provider :virtualbox do |vb, override|
    vb.memory = 2048
  end

  # there are obviously vagrant versions with a
  # broken 'docker' provisioner that can be fixed
  # by invoking an 'apt-get update' *before* docker itself
  config.vm.provision "shell", inline: "apt-get update"

  # fetch the ubuntu:latest image that is required for
  # the test suite
  config.vm.provision "docker",
    images: ["ubuntu:trusty"]

  # kick off the tests automatically
  config.vm.provision "shell", inline: script
end
