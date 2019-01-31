#!/usr/bin/env python2.7
"""
generate files to deploy libvirt vms and nws, possibly in a docker environment
"""
from __future__ import print_function

import logging
import os
import shutil
import sys
import shlex
import argparse
from copy import deepcopy
from enum import Enum
from lxml import etree

import argh
from argh.decorators import arg, named
from argh.exceptions import CommandError
from etconfig import ElementConfError, load, id2elt
from qdeploy.utils import cmd, resource_path

try:  # py3
    from shlex import quote as sh_quote
except ImportError:  # py2
    from pipes import quote as sh_quote


# pylint: disable=invalid-name
logger = logging.getLogger(__name__)
logging.basicConfig(handlers=[logging.StreamHandler()], level=logging.DEBUG)

conf = None

# directory containing
# - the files needed to build the docker container
# -
QDEPLOY_RESOURCES_DIR = ".qdeploy"
QDEPLOY_CONF = "./qdeploy.conf"
QDEPLOY_DEFAULT_CONTAINER_NAME = "qdeploy"


def vm_extend(vm, vm_defaults):
    """add to vm the parameters from vm_defaults that are not defined in
    vm.

    :param vm: Element representing the vm parameters
    :param vm_defaults: Element representing the vm default parameters

    """
    for arg_i in list(vm_defaults):
        if vm.find(arg_i.tag) is None:
            vm.append(deepcopy(arg_i))


def get_vm_group(group_name):
    """find a group of name in conf
    """
    root = conf
    elems = root.findall('./group[name="{}"]/vm'.format(group_name))
    if elems is None:
        return []
    res_elem_list = [e.text for e in elems]
    return res_elem_list

def find_elem_list(tag, name_list, _all=False):
    """find a list of Element with:

    :param tag: Element tag to find
    :param name_list: names of Element to find
    :param _all:  (Default value = False)

    The form is:
    <{tag}><name>text</name></{tag}>
    """
    if name_list is None:
        name_list = []
    root = conf
    res_elem_list = []

    if _all and len(name_list) > 0:
        raise CommandError("Cannot have both '-all' and a list of names")

    if not _all and len(name_list) == 0:
        raise CommandError("Must have either '-all' or a list of names")

    for name in name_list:
        res = root.find('./{}[name="{}"]'.format(tag, name))
        if res is None:
            raise CommandError("{} '{} not found'".format(tag, name))
        res_elem_list.append(res)

    if _all:
        res_elem_list = root.findall(tag)

    return res_elem_list


def generate_network_xml_file(resource_dir, nw):
    """generate libvirt xml file to defina a network

    :param resource_dir: target directory
    :param nw: Element representing the xml to produce

    :returns: the absolute path+name of the file
    """
    name = nw.find('name').text
    xml = etree.tostring(nw, pretty_print=True)
    xml_file_name = os.path.join(resource_dir, "nw-" + name + ".xml")
    print(xml_file_name)
    print(os.getcwd())
    with open(xml_file_name, 'w+') as xml_file:
        xml_file.write(xml)
    return xml_file_name


def is_running_in_docker():
    """check if the qdeploy.conf file defines a docker environment
    """
    root = conf
    docker = root.find("docker")
    return docker is not None

def run_in_container(a_cmd, _interactive=False, _detached=False):
    """execute a system command possibly inside the docker container

    :param a_cmd:
    :param _interactive:  (Default value = False)

    """
    if is_running_in_docker():
        opts = "-ti" if _interactive else "-t"
        container_name = get_container_name()
        if not container_name:
            raise CommandError("No docker container name defined in qdeploy.conf")

        container_exec = ["docker", "exec", opts, container_name]
        if isinstance(a_cmd, str):
            a_cmd = shlex.split(a_cmd)
        cmd_to_execute = container_exec + a_cmd
    else:
        cmd_to_execute = a_cmd

    res = cmd(cmd_to_execute, _log=logger, _detached=_detached)
    if _detached:
        res.wait()

    res.print_on_error()
    return res



def generate_virt_install_cmd(vm, vm_defaults, extra_args=None):
    """generate vm xml using virt-install

    :param vm: Element node representing vm
    :param vm_defaults:
    :returns: an array representing the virt-install command to import
    the vm.

    """

    if not extra_args:
        etree.SubElement(vm, 'import')
        extra_args = []

    # etree.SubElement(vm, 'transient')
    # etree.SubElement(vm, 'noautoconsole')
    cmd_array = ['virt-install']
    name = vm.find('name').text

    if vm_defaults is not None:
        vm_extend(vm, vm_defaults)

    if vm.find("disk") is None:
        # assume:
        # 1. cwd mounted in the same location in docker
        # 2. a qcow2 exist with the name of the vm
        disk_element = etree.SubElement(vm, 'disk')
        disk_element.text = os.path.join(os.getcwd(), name + ".qcow2")

    for arg_i in list(vm):
        cmd_array.append('--' + arg_i.tag)
        val = None
        if arg_i.attrib:
            attrs = ",".join(["{}={}".format(k, v) for k, v in arg_i.attrib.items()])
            val = attrs
        else:
            val = arg_i.text

        if val:
            cmd_array.append(sh_quote(val))

    cmd_array = cmd_array + extra_args

    return cmd_array


def get_container_name():
    """get container name from conf file or default name 'qdeploy' if
    none provided
    """
    root = conf
    name_node = root.find("docker/name")
    if name_node is None:
        return None

    if not name_node.text:
        return QDEPLOY_DEFAULT_CONTAINER_NAME

    return name_node.text

def do_start_docker():
    """start docker container by calling the .qdeploy/start_docker.sh
    script
    """
    mounts = ""
    use_x11 = "false"

    root = conf
    container_name = get_container_name()
    if not container_name:
        raise CommandError("No docker container name defined in qdeploy.conf")

    for m in root.iterfind("docker/mount"):
        mount = m.text if ":" in m.text else m.text + ":" + m.text
        mounts += " -v " + mount


    x11_node = root.find("docker/x11")
    if x11_node is not None:
        use_x11 = x11_node.text

    # os.chdir()
    res = cmd(["start_docker.sh", container_name, use_x11, mounts],
              _log=logger, _cwd=QDEPLOY_RESOURCES_DIR)
    res.exit_on_error()

def do_stop_docker():
    """stop docker container by calling the .qdeploy/stop_docker.sh
    script
    """
    os.chdir(QDEPLOY_RESOURCES_DIR)
    container_name = get_container_name()
    if not container_name:
        raise CommandError("No docker container name defined in qdeploy.conf")

    res = cmd("stop_docker.sh {container}", container=container_name, _log=logger)
    res.print_on_error()
    print(res.out)



def do_start_nw(nw):
    """define and start a network

    :param nw: Element representing the network in libvirt format

    """
    xml_file_name = generate_network_xml_file(QDEPLOY_RESOURCES_DIR, nw)
    name = nw.find('name').text

    abs_path = os.path.join(os.getcwd(), xml_file_name)
    # assume xml_file_name mounted in docker at the same location
    run_in_container(["virsh", "net-define", "--file", abs_path])
    run_in_container(["virsh", "net-start", name])


def do_stop_nw(nw):
    """stop and undefine a network

    :param nw: Element representing the network in libvirt format

    """
    # xml_file_name = generate_network_xml_file(QDEPLOY_RESOURCES_DIR, nw)
    name = nw.find('name').text

    # abs_path = os.path.join(os.getcwd(), xml_file_name)
    # assume xml_file_name mounted in docker at the same location
    run_in_container(["virsh", "net-destroy", name])
    run_in_container(["virsh", "net-undefine", name])

def do_start_vm(vm, extra_args=None):
    """start a vm using virt-install

    :param vm: Element representing the vm (xml Element that can be
    directly converted to virt-install command line)

    """
    root = conf
    vm_defaults = root.find("vm_defaults")
    virtinst_cmd = generate_virt_install_cmd(vm, vm_defaults, extra_args)
    res = run_in_container(virtinst_cmd)
    return res


class StopMode(Enum):
    """
    possible modes to stop a vm
    """
    DESTROY = 1
    SHUTDOWN = 2
    REBOOT = 3

def do_stop_vm(vm, stop_mode=StopMode.DESTROY):
    """undefine and stop a vm

    :param vm: Element representing the vm. Only the name is actually
    needed here.

    """
    # root = conf
    name = vm.find('name').text

    if stop_mode == StopMode.DESTROY:
        run_in_container(["virsh", "destroy", name])
        run_in_container(["virsh", "undefine", name])
    elif stop_mode == StopMode.SHUTDOWN:
        run_in_container(["virsh", "shutdown", name])
        run_in_container(["virsh", "undefine", name])
    elif stop_mode == StopMode.REBOOT:
        run_in_container(["virsh", "reboot", name])
    else:
        print("internal error invalid stop mode")


def assert_conf():
    """
    check if config file has been loaded successfully or exit on error
    """
    global conf
    if conf is None:
        sys.exit(1)

#----------------------------------------------------------------------
# CLI commands
#----------------------------------------------------------------------


@named("dump")
def cmd_dumpconf():
    """dump qdeploy.conf to xml. debug purpose"""
    global conf
    assert_conf()
    print(conf.toxml())

@named("init")
def cmd_init(force=False):
    """writes files needed by 'env-start' to '.qdeploy/' directory
    """
    # :param force: overwrite existing conf if True (Default value =
    # False)
    assert_conf()
    resources_path = resource_path('resources')

    if os.path.isdir(QDEPLOY_RESOURCES_DIR):
        if force:
            shutil.rmtree(QDEPLOY_RESOURCES_DIR)
        else:
            print ("Error: {} already existing. use -force".
                   format(QDEPLOY_RESOURCES_DIR))
            sys.exit(1)

    print("=> Copying resources to {resources}".format(
        resources=QDEPLOY_RESOURCES_DIR))
    shutil.copytree(resources_path, QDEPLOY_RESOURCES_DIR)


@named("start")
def cmd_start():
    """
    start docker environment, then all networks and all vms
    """
    assert_conf()
    cmd_init(force=True)
    cmd_start_env()
    cmd_start_nw(net_names=None, start_all=True)
    cmd_start_vm(vm_names=None, start_all=True)


@named("stop")
def cmd_stop():
    """
    stop docker environment, then all networks and all vms
    """
    assert_conf()
    cmd_stop_env()



@named("env-start")
def cmd_start_env():
    """
    start docker container
    """
    assert_conf()
    root = conf

    if is_running_in_docker():
        do_start_docker()
        for c in root.iterfind("docker/start_cmd"):
            run_in_container(c.text)


    for c in root.iterfind("start_cmd"):
        cmd(c.text, _log=logger)

@named("env-stop")
def cmd_stop_env():
    """
    stop docker container
    """
    assert_conf()
    root = conf

    if is_running_in_docker():
        do_stop_docker()
        for c in root.iterfind("docker/stop_cmd"):
            run_in_container(c.text)

    for c in root.iterfind("stop_cmd"):
        cmd(c.text, _log=logger)


@named("vm-list")
def cmd_list_vm():
    """display vms in qdeploy.conf
    """
    # :param list_all:  (Default value = False)
    assert_conf()
    root = conf
    for n in root.iterfind("vm/name"):
        print(n.text)

@named("net-list")
def cmd_list_nw():
    """display networks in qdeploy.conf
    """
    # :param net_names:
    # :param list_all:  (Default value = False)
    assert_conf()
    root = conf
    for n in root.iterfind("network/name"):
        print(n.text)


@named("vm-start")
@arg("vm_names", nargs='*')
@arg("-a", "--all", dest="start_all")
def cmd_start_vm(vm_names, start_all=False, group=None):
    """start one or several vms
    """
    # :param vm_names: list of vm names
    # :param start_all: start all if True (Default value = False)
    assert_conf()
    if group is not None:
        vm_names = get_vm_group(group)

    vm_list = find_elem_list("vm", vm_names, start_all)
    for vm in vm_list:
        do_start_vm(vm)

@named("vm-install")
@arg("vm_name")
@arg('args', nargs=argparse.REMAINDER, help="extra virt-install args")
def cmd_install_vm(vm_name, args):
    """install a vm
    """
    # :param vm_name: list of name to install
    # :param rest: install parameters
    assert_conf()
    print(args)
    vm_list = find_elem_list("vm", [vm_name])
    do_start_vm(vm_list[0], args)

@named("vm-stop")
@arg("vm_names", nargs='*', help="names of the vms to stop")
@arg("-a", "--all", dest="stop_all", help="stop all vms defined in qdeploy.conf")
@arg("-s", "--shutdown")
@arg("-r", "--reboot")
def cmd_stop_vm(vm_names, stop_all=False, shutdown=False, reboot=False, group=None):
    """stop and undefine one or several vms. By default the vm  is destroyed.
    """
    assert_conf()
    if shutdown and reboot:
        raise CommandError("Cannot have both '--shutdown' and '--reboot'")

    if shutdown:
        stop_mode = StopMode.SHUTDOWN
    elif reboot:
        stop_mode = StopMode.REBOOT
    else:
        stop_mode = StopMode.DESTROY

    if group is not None:
        vm_names = get_vm_group(group)

    vm_list = find_elem_list("vm", vm_names, stop_all)
    for vm in vm_list:
        do_stop_vm(vm, stop_mode)


@named("net-start")
@arg("net_names", nargs='*')
@arg("-a", "--all", dest="start_all")
def cmd_start_nw(net_names, start_all=False):
    """
    start one or several networks
    """
    # :param net_names:
    # :param start_all:  (Default value = False)
    assert_conf()
    nw_list = find_elem_list("network", net_names, start_all)
    for nw in nw_list:
        do_start_nw(nw)

@named("net-stop")
@arg("net_names", nargs='*', help="names of the networks to stop")
@arg("-a", "--all", dest="stop_all", help="stop all networks defined in qdeploy.conf")
def cmd_stop_nw(net_names, stop_all=False):
    """stop and undefine a network
    """
    # :param net_names:
    # :param stop_all:  (Default value = False)
    assert_conf()
    nw_list = find_elem_list("network", net_names, stop_all)
    for nw in nw_list:
        do_stop_nw(nw)

@named("virtmgr")
def cmd_start_virtmgr():
    """start the virt-manager. Only possible in docker if using X11"""
    assert_conf()
    run_in_container(["virt-manager"])

@named("sh")
@arg('cmd_to_execute', nargs=argparse.REMAINDER)
def cmd_start_sh(cmd_to_execute):
    """start a shell or a shell command in docker container
    """
    # :param cmd_to_execute:
    assert_conf()
    if cmd_to_execute:
        cmd_lst = ["bash", "-c", " ".join(cmd_to_execute)]
        run_in_container(cmd_lst, _interactive=True, _detached=True)
    else:
        cmd_lst = ["bash"]
        run_in_container(cmd_lst, _interactive=True, _detached=True)

# @named("virsh")
# @arg('virsh_args', nargs=argparse.REMAINDER,
#      help="virsh sub-command (e.g. 'net-list')")
# def cmd_virsh(virsh_args):
#     """execute virsh in docker container
#     """
#     # :param virsh_args: virsh sub-command (e.g. 'net-list')
#     assert_conf()
#     run_in_container(['bash', '-c', "virsh"] + virsh_args, _interactive=True)

def main():
    """entry point"""
    global conf

    try:
        id_mapper = id2elt("name")
        conf = load(QDEPLOY_CONF, id_mapper=id_mapper)
    except ElementConfError as exc:
        print("Syntax error in {}: {}".format(QDEPLOY_CONF, exc))
        sys.exit(1)
    except IOError:
        print("Warning: qdeploy.conf is missing in current directory")

    parser = argh.ArghParser()
    parser.add_commands([cmd_dumpconf, cmd_init, cmd_start_env, cmd_stop_env,
                         cmd_start_vm, cmd_install_vm, cmd_stop_vm, cmd_list_vm,
                         cmd_start_nw, cmd_stop_nw, cmd_list_nw,
                         cmd_start_virtmgr, cmd_start_sh,
                         cmd_start, cmd_stop])
    parser.dispatch()


if __name__ == '__main__':
    main()
