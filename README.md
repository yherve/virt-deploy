
Introduction
--------------

virt-deploy is a script that to deploy a set of virtual machines in
libvirt and create the network topology with a single config
file. 

It can create a docker container for you and deploy the vms and the
networks inside the container, which is useful to isolate a test setup
for instance. The config of docker is inspired by
[libvirtd-in-docker](https://github.com/fuzzyhandle/libvirtd-in-docker).


Requirements
-------------

- libvirt installed and running correctly on local host

- docker installed and running correctly on local host (optional)

- already created bootable qcow2 vm images. The simplest way to create
  such image is via the usual virt-install script.

- edit "qdeploy.conf" to describe the vms and the networks to deploy


Installation
-------------

The virt-deploy tool is written in python 2.7.

The easiest way to install is to use the provided Makefile to generate
a standalone binary. The requirements are python 2.7, pip,virtualenv
and make


To generate the binary:

    $ make

The result binary "./dist/virt-deploy" can now be copied in any
convenient place, e.g. ~/bin or /usr/local/bin

Check:

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

It is recommanded to get familiar with the script running directly in
the host before trying to deploy in a docker env.

the virt-deploy script must be started in the directory containing
  both the qcow2 images and the qdeploy.conf file

In this example, we use virt-deploy to start a vm and 2 networks (aka
bridges) directly in the local host.

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

Check:

    ls -l .qdeploy/


### create and start the network

    $ virt-deploy net-start -a

Check (1):

    $ virsh net-list
     Name                 State      Autostart     Persistent
    ----------------------------------------------------------
     lan1                 active     no            yes
     lan2                 active     no            yes

Note that the xml files needed by libvirt to create the network are
under .qdeploy/ directory.

Check (2):

    $ brctl show

### create and start the vm

    $ virt-deploy vm-start -a

Check (1):

    $ virsh list
    Id    Name                           State
    ----------------------------------------------------
    2     mydeb                          running

Check (2):

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

The 'network' part allows to create one or many networks.

It corresponds exactly to the [libvirt network
format](https://libvirt.org/formatnetwork.html) translated to a
simpler config format (see syntax section below).

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

The 'vm' part permits to create one or several virtual machines (aka
'domains' in libvirt). Under the hood, we use 'virt-install' to create
and start a virtual machine.

In our qdeploy.conf config file, the attributes of the 'vm' element
corresponds to the
[virt-install](https://linux.die.net/man/1/virt-install) command line
parameters.

More specifically, virt-install parameters are translated into:

- an element with the name of the parameters
- a text attribute with the value of the parameter
- a mandatory semi column

Example

    ram 4096;

If the parameter attribute is a comma-separated key-value list, it is
possible to pass a list of attributes, which might be more readable.

Example

    network {
            network=mgtnw1;
            mac=52:54:00:00:01:07;
            model=e1000;
        }

Full example

If you want to start a vm like so:

    $ virt-install --name vm1 --ram 4000 --vcpus 2 --graphics vnc \
                   --network "network=mgtnw1,mac=52:54:00:00:01:07,model=e1000" \
                   --disk "./vm1.qcow2" --noautoconsole

Use the description below in qdeploy.conf

    vm vm1 {
        ram 4000;
        vcpus 2;
        graphics vnc;
        noautoconsole;
        network {
            network=mgtnw1;
            mac=52:54:00:00:01:07;
            model=e1000;
        }
    }

Note that if the "disk" element is not specified, the script assumes
that a 'qcow2' file exist with the name of the vm in the current working
directory.

So in this case, the extra parameter is implicitly added:

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

Example:

    docker "mycontainer" {
        mount "/data/qemu/vmtest";
        mount "/data/qemu/base";
        x11 true;
        start_cmd "iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE";
    }

'mount' indicates which directories should be made available to the
container (at least the current directory).

'x11' specifies if you want to be able to open x11 applications inside
the container, which is especially useful for virt-manager.

'start_cmd' is any bash command you want to start inside the container
when the container starts. Here I specify that all the traffic leaving
the container should have the address of the container.


#### start_cmd and stop_cmd

It is possible to execute bash commands directly on the host when the
docker container is started.

     start_cmd "sudo ip route add 192.168.100.0/24 via 172.17.0.2";
     stop_cmd "sudo ip route del 192.168.100.0/24 via 172.17.0.2";

In this example, I set a route to access the network I have created
from my host via the docker container.


### syntax of the config file

The file uses a very simple format which translates
directly to xml. see [here](https://github.com/yherve/etconfig).

Note that contrary to xml, the double quotes can be omitted for
'simple' attributes such as number, ip addresses and identifiers
(more generally, letters and digits without spaces).
In doubt, always use double quote.


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

Edit the qdeploy.conf to add a 'docker' section.

Change the 'mount' section to mount the current directory to docker
(In my example, I have to mount 2 directories because my image is
linked to a base image in another directory).

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

Checks:

    $ docker ps
    $ virt-deploy sh systemctl status libvirtd
    $ virt-deploy sh virsh list


### start the network

    virt-deploy net-start -a

Check

    $ virt-deploy sh virsh net-list
     Name                 State      Autostart     Persistent
    ----------------------------------------------------------
     lan1                 active     no            yes
     lan2                 active     no            yes

### create and start the vm

    $ virt-deploy vm-start -a

Check (1):

    $ virt-deploy sh virsh list
    Id    Name                           State
    ----------------------------------------------------
    2     mydeb                          running


### connecting using host virsh and virtmgr clients

Get the docker ip address (eg docker inspect), and enter the following
command

    virt-manager -c qemu+tcp://172.17.0.2/system

You should see your virtual machine 'mydeb'. If you click on it, the
display should appear. Check that the machine has internet access
(because we set forward mode to nat in the example above).

If you always connect to the same container, it is easier to set an
environment variable:

    export VIRSH_DEFAULT_CONNECT_URI='qemu+tcp://172.17.0.2/system'

You can now use virsh as usual from the host

    $ virsh list
    Id    Name                           State
    ----------------------------------------------------
     1     mydeb                          running


### connecting via the container

The 'virt-deploy sh' command is simply an alias to enter a running
container (docker exec). You can use it to interact with libvirtd
directly:

#### virsh

    $ virt-deploy sh virsh list
     Id    Name                           State
    ----------------------------------------------------
     1     mydeb                          running


#### ssh to the machine

    virt-deploy sh ssh 192.168.100.104

#### virt-manager

If you have the x11 socket available from the container, you can also
start the virt-manager directly in the countainer and get the display
of your machine:

There is an alias to do this

    virt-deploy virtmgr


### Setting a route from the host to the container

This is useful if you need to scp to a vm for example.

The first thing to do is to add a route on the host to reach the
internal network via docker. This can be done automatically by adding
the following lines at the beginning of the qdeploy.conf file.

     start_cmd "sudo ip route add 192.168.100.0/24 via 172.17.0.2";
     stop_cmd "sudo ip route del 192.168.100.0/24 via 172.17.0.2";

Unfortunately, this is not sufficient. Now if you try to ssh to your
vm, you'll get an error. The reason is that when you configure a
libvirt network with a forward mode 'nat', it also creates iptable
rules to prevent the outside from accessing the network.

So you have 2 options:
- remove the iptable rule set by libvirt
- use regular routing and configure masquerading yourself.

I prefer the second approach, so the config now becomes:


    start_cmd "sudo ip route add 192.168.100.0/24 via 172.17.0.2";
    stop_cmd "sudo ip route del 192.168.100.0/24 via 172.17.0.2";
    docker "mycontainer" {
        mount "/data/qemu/vmtest";
        mount "/data/qemu/base";
        start_cmd "iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE";
    }
    network "mgtnw1" {
        bridge.name="mgtnw1"
        forward.mode=route
        ip.address=192.168.100.1
        ip.netmask=255.255.248.0
        ip.dhcp.range {start=192.168.100.100 end=192.168.100.253}
    }


With this config, you should be able to access your vm started in
docker directly from your host.
