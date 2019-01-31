
Introduction
--------------

virt-deploy is a script that is able to deploy a set of virtual
machines in libvirt and create the network topology.

It is possible to deploy these vms directly to the environment
specified by VIRSH_DEFAULT_CONNECT_URI (e.g. directly on the host) or
it is possible to deploy the all the vms and the networks inside a
docker container.

It is recommanded to get familiar with the script running directly in
the host before trying to deploy in a docker env.


Requirements
-------------
- libvirt installed and running correctly (not needed if you run in
  docker)

- The virt-deploy script needs already created bootable vm images (eg
  qcow2). The simplest way to create such image is via the usual
  virt-install script.

- qdeploy.conf describes the vms and the networks to deploy

- the virt-deploy script must be started in the directory containing
  both the qcow2 images and the qdeploy.conf file


Installation
-------------

The virt-deploy tool is written in python 2.7.

The easiest way to install is to use the Makefile to generate a
standalone binary. The requirements are python 2.7, pip,virtualenv and
make

To generate the binary:

    $ make

The result binary "./dist/virt-deploy" can now be copied in any
convenient place, e.g. ~/bin or /usr/local/bin

Verification:

    $ ./dist/virt-deploy
    Warning: qdeploy.conf is missing in current directory
    usage: virt-deploy [-h]
                       {dump,init,env-start,env-stop,vm-start,vm-install,
                        vm-stop,net-start,net-stop,net-list,vm-list,virsh,
                        virtmgr,sh,start,stop}
                       ...
    virt-deploy: error: too few arguments


Dev environment
--------------

    . use_venv.sh

This will enter the virtualenv and define a bash alias 'virt-deploy'
that executes the code directly in source tree


Quick start
---------------

In this example, we use virt-deploy to start a vm and 2 networks (aka
bridges) on the local host.

The first bridge:

- has an ip address 192.168.100.1
- starts a dhcp server (dnsmasq) to server address in range [100-254]
- sets iptable rules to masquerade outgoing traffic

The vm has 2Gb ram, 2cpus and a vnc display

### prerequisites

- The example below assumes you already have created a debian image
'mydeb.qcow2' (eg using virt-install)

- libvirt has been installed and running correctly in the local host
  (check systemctl status libvirtd)

### create deployment config file

paste the content below in 'qdeploy.conf' (see section below for an
explanation of the syntax).

The noautoconsole is important. It tells the vm to start without
showing the vm display. The vm display can later be obtained using the
virt-manager.

The reason why 'noautoconsole' is so important is because of a
bug/feature: if you don't specify 'noautoconsole', virt-deploy will
wait for the vm terminates, which is a problem if you start multiple
vms at once.

    network "lan1"{
        bridge.name="lan1"
        forward.mode=nat
        ip.address=192.168.100.1
        ip.netmask=255.255.255.0
        ip.dhcp.range {start=192.168.100.100 end=192.168.100.254}
    }

    network "lan2"{
        bridge.name="lan2"
    }

    vm "mydeb" {
        ram 2048;
        vcpus 2;
        graphics vnc;
        noautoconsole;
        network  {network=lan1 model=e1000}
        network  {network=lan2 model=e1000}
    }


### initialization

    $ virt-deploy init

This creates a hidden '.qdeploy' directory (which is mostly needed if
using docker)

Verification:

    ls -l .qdeploy/


### create and start the network

    $ virt-deploy net-start -a

Verification (1):

    $ virsh net-list
     Name                 State      Autostart     Persistent
    ----------------------------------------------------------
     lan1                 active     no            yes
     lan2                 active     no            yes

Note that the xml files needed by libvirt to create the network are
under .qdeploy/ directory.

Verification (2):

    $ brctl show

### create and start the vm

    $ virt-deploy vm-start -a

Verification (1):

    $ virsh list
    Id    Name                           State
    ----------------------------------------------------
    2     mydeb                          running

Verification (2):

Start virt-manager and click on 'mydeb', you should see the display.

- Check the ip address is 192.168.100.100
- Check the default route via 192.168.100.1
- Check the dns is 192.168.100.1
- Check the virtual machine 'details' panel (cpu, memory, ...)



virt-deploy command line
----------------------

### Initialization

creates a .qdeploy/ hidden directory

    $ virt-deploy init

### Start network

start all networks

    $ virt-deploy net-start -a

start selected networks

    $ virt-deploy net-start nw1 nw2

### Stop networks

Stopped network are unregistered from libvirt.

stop all networks

    $ virt-deploy net-stop -a

stop selected networks

    $ virt-deploy net-stop nw1 nw2

### Start vms

start all vms

    $ virt-deploy vm-start -a

start selected vms

    $ virt-deploy vm-start vm1 vm2

### Stop vms

stop all vms

    $ virt-deploy vm-stop -a

stop selected vms

    $ virt-deploy vm-stop vm1 vm2


virt-deploy config file
-------------------------

This section describes the qdeploy.conf configuration file. This file
describes the networks and the virtual machines you want to deploy.

It offers a consistent representation of the information that would
otherwise be scattered in many xml files (one per network, see virsh
net-define) and many shell commands (one per vm, see virt-install).

The idea is to register all the resource to libvirt at once and to
unregister them also at once.

### description

The 'qdeploy.conf' file is composed of 'network', 'vm', 'vm_defaults'
and 'docker' sections. network and vm are mandatory.

#### network

The 'network' part corresponds exactly to the [libvirt
network format](https://libvirt.org/formatnetwork.html) translated to
a simpler config format (see syntax section below).

Example:

    network "mgtnw1" {
        bridge.name="mgtnw1"
        forward.mode=nat
        ip.address=192.168.202.1
        ip.netmask=255.255.248.0
        ip.dhcp.range {start=192.168.202.100 end=192.168.202.253}
        ip.dhcp.host  {mac=52:54:00:00:01:07  ip=192.168.202.161}
        ip.dhcp.host  {mac=52:54:00:00:01:0B  ip=192.168.202.192}
    }

In this example, the network has nat translation and a dhcp server.
Some machines have fixed reserved addresses.



#### vm

The 'vm' part corresponds to the
[virt-install](https://linux.die.net/man/1/virt-install) command line
parameters.

Desired parameters are translated into

- an element with the name of the parameters
- a text attribute with the value of the parameter

If the parameter attribute is a comma-separated key-value list (as in
the network example below), it is possible to pass a list of attributes

Example

If you want to start a vm like so:

    $ virt-install --name vm1 --ram 4000 --vcpus 2 --graphics vnc \
                   --network "network=mgtnw1,mac=52:54:00:00:01:07,model=e1000" \
                   --disk "./vm1.qcow2"

use the description below in qdeploy.conf

    vm vm1 {
        ram 4000;
        vcpus 2;
        graphics vnc
        network "network=mgtnw1,mac=52:54:00:00:01:07,model=e1000";
    }

or, if you prefer to expand the network parameter:

    vm vm1 {
        ram 4000;
        vcpus 2;
        graphics vnc;
        network {
            network=mgtnw1;
            mac=52:54:00:00:01:07;
            model=e1000;
        }
    }

Note that if the "disk" element is not specified, the script assumes
that a qcow2 file exist with the name of the vm in the current working
directory.

In this case is implicitly added:

    disk "./vm1.qcow2"


#### vm_defaults

The vm_defaults section can be used to set the properties common to
all vms. The syntax is the same as 'vm'

Example:

     vm_defaults {
         ram  4000;
         graphics "spice,listen=0.0.0.0";
         noautoconsole;
         transient;
     }

This example means that all the vms:

- have 4Gb
- use spice display
- do not show the display at startup
- are unregistered they are stopped




#### docker

The docker element allows to start a container that isolates the vms
and the networks you create.


### syntax

The file uses a very simple format called
[etconfig](https://github.com/yherve/etconfig), which translates
directly to xml.

Note that contrary to xml, the double quotes can be omitted for
'simple' elements (without space) such as number, ip addresses, dates,
identifiers (in doubt, always use double quote).


|description        | etconfig format       |   xml format                           |
|-------------------|---------------------- |----------------------------------------|
|element            |  network{  }          | &lt;network>&lt;/network>              |
|element(1)         |  network;             | &lt;network/>                          |
|attributes(2)      |  network{ipv6="yes"}  | &lt;network ipv6="yes">&lt;/network>   |
|name attribute(3)  |  network "nw1" {}     | &lt;network name="nw1">&lt;/network>   |
|text               |  ram {"4096"}         | &lt;ram>4096&lt;/ram>                  |
|text(4)            |  ram 4096;          | &lt;ram>4096&lt;/ram>                  |
|nested elements    | dhcp{ host {ip=""} }  |&lt;dhcp> &lt;host ip="">&lt;/host>&lt;/dhcp>|
|nested elements(5) | dhcp.host.ip=""       |&lt;dhcp> &lt;host ip="">&lt;/host>&lt;/dhcp>|
|comments           |# this is a comment    | &lt;!-- this is a comment -->          |
|multi-line comments|/* this is a comment */| &lt;!-- this is a comment -->          |


(1) if the element does not have attributes or nested-elements,
brackets can be avoided (but a ';' is needed)

(2) note that an optional trailing ';' can be added to make separation
between attributes clearer (e.g name="foo"; color="red"; )

(3) special simplified syntax for attribute called "name". It can be
used only with the "brackets" form of element. This is syntactic
sugar, you don't have to use it if it confuses you.

(4) if the text attribute is the only sub-element, brackets can be
avoided (but a ';' is needed)

(5) if the nested elements are unique, it is possible to use a dotted notation




using virt-deploy with with docker
------------------

### config docker in qdeploy.conf

The example below is the same example as in quick start before, except
that we say we want our networks and our vms to be started in a docker
container, which permits to run several simulations on your host
without interference.

    docker "mycontainer" {
        mount "/data/qemu/tuto";
        mount "/data/qemu/base";
        x11 true;
    }

    network "lan1"{
        bridge.name="lan1"
        forward.mode=nat
        ip.address=192.168.100.1
        ip.netmask=255.255.255.0
        ip.dhcp.range {start=192.168.100.100 end=192.168.100.254}
    }

    network "lan2"{
        bridge.name="lan2"
    }

    vm "mydeb" {
        ram 2048;
        vcpus 2;
        graphics vnc;
        noautoconsole;
        network  {network=lan1 model=e1000}
        network  {network=lan2 model=e1000}
    }



The steps to deploy your environment in docker are:

### start the docker container

    $ virt-deploy env-start

Verifications:

    $ docker ps
    $ virt-deploy sh systemctl status libvirtd
    $ virt-deploy sh virsh list

The other steps are similar to the quick start guide

### start the network

    virt-deploy net-start -a

Verification

    $ virt-deploy sh virsh net-list
     Name                 State      Autostart     Persistent
    ----------------------------------------------------------
     lan1                 active     no            yes
     lan2                 active     no            yes

### create and start the vm

    $ virt-deploy vm-start -a

Verification (1):

    $ virt-deploy sh virsh list
    Id    Name                           State
    ----------------------------------------------------
    2     mydeb                          running


### connecting using host virsh/virtmgr


When using a docker container, you can:

- start a bash session in the docker container, then use the usual
libvirt commands such as virsh or virt-manager

- or run virsh directly from your host (you need to install
  libvirt-clients and virt-manager), then set the
  VIRSH_DEFAULT_CONNECT_URI as below.

    export VIRSH_DEFAULT_CONNECT_URI='qemu+tcp://172.17.0.2/system'
