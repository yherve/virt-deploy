
### virt-deploy start

the virt-deploy start is used to create the docker environment, then
the networks and the virtual machines at once. It has has a race
condition, and the creation of the networks fails because the docker
container is not yet ready.

So for now, start the elements one by one:

    virt-deploy env-start
    virt-deploy net-start -a
    virt-deploy vm-start -a

### virt-deploy vm-start blocks after launching the first vm

When creating a virtual machine, the 'noautoconsole' parameter is
mandatory else the first virt-install will block. I should either
start the 'virt-install' in background or always add the
'noautoconsole' parameter/
