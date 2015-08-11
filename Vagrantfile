
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
apt-get -y install lxc python-pip python-virtualenv

if (source /etc/default/docker && [[ $DOCKER_OPTS != *lxc* ]]); then

  echo "Adjusting docker configuration to use LXC driver, and restarting daemon." >&2

  echo '# Blockade requires the LXC driver for now' >> /etc/default/docker
  echo 'DOCKER_OPTS="$DOCKER_OPTS -e lxc"' >> /etc/default/docker
  service docker restart

fi

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

  config.vm.network "forwarded_port", guest: 9200, host: 9200
  config.vm.network "forwarded_port", guest: 9201, host: 9201
  config.vm.network "forwarded_port", guest: 9202, host: 9202

  config.vm.provider :virtualbox do |vb, override|
  end

  config.vm.provision "docker",
    images: ["ubuntu"], version: "1.6.2"

  # kick off the tests automatically
  config.vm.provision "shell", inline: script
end
