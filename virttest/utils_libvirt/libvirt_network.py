
"""
Virsh net* command related utility functions
"""
import re
import logging

from avocado.core import exceptions
from avocado.utils import process

from virttest import virsh
from virttest import remote
from virttest.utils_test import libvirt


def create_or_del_network(net_dict, is_del=False, remote_args=None):
    """
    Create or delete network on local or remote

    :param net_dict: Dictionary with the network parameters
    :param is_del: Whether the networks should be deleted
    :param remote_args: The parameters for remote
    """

    remote_virsh_session = None
    if remote_args:
        remote_virsh_session = virsh.VirshPersistent(**remote_args)

    if not is_del:
        net_dev = libvirt.create_net_xml(net_dict.get("net_name"), net_dict)

        if not remote_virsh_session:
            if net_dev.get_active():
                net_dev.undefine()
            net_dev.define()
            net_dev.start()
        else:
            remote_ip = remote_args.get("remote_ip")
            remote_user = remote_args.get("remote_user")
            remote_pwd = remote_args.get("remote_pwd")
            if not all([remote_ip, remote_user, remote_pwd]):
                raise exceptions.TestError("remote_[ip|user|pwd] are necessary!")
            remote.scp_to_remote(remote_ip, '22', remote_user, remote_pwd,
                                 net_dev.xml, net_dev.xml, limit="",
                                 log_filename=None, timeout=600,
                                 interface=None)
            remote_virsh_session.net_define(net_dev.xml, debug=True)
            remote_virsh_session.net_start(net_dict.get("net_name"),
                                           debug=True)
            remote.run_remote_cmd("rm -rf %s" % net_dev.xml, remote_args)
    else:
        virsh_session = virsh
        if remote_virsh_session:
            virsh_session = remote_virsh_session
        if net_dict.get("net_name") in virsh_session.net_state_dict():
            virsh_session.net_destroy(net_dict.get("net_name"),
                                      debug=True, ignore_status=True)
            virsh_session.net_undefine(net_dict.get("net_name"),
                                       debug=True, ignore_status=True)
    if remote_virsh_session:
        remote_virsh_session.close_session()


def check_established(params):
    """
    Parses netstat output for established connection
    on remote or local

    :param params: the parameters used
    :return: str, the port used
    :raises: exceptions.TestFail if no match
    """
    port_to_check = params.get("port_to_check", "4915")
    check_local = 'yes' == params.get("check_local_port", "no")
    ipv6_config = "yes" == params.get("ipv6_config", "no")
    if ipv6_config:
        server_ip = params.get("ipv6_addr_des", "")[:17]
    else:
        server_ip = params.get("server_ip", params.get("remote_ip"))

    cmd = "netstat -tunap|grep %s" % port_to_check
    if check_local:
        cmdRes = process.run(cmd, shell=True)
    else:
        cmdRes = remote.run_remote_cmd(cmd, params)

    if port_to_check != '4915':
        pat_str = r'.*%s:%s.*ESTABLISHED.*qemu-kvm.*' % (server_ip,
                                                         port_to_check)
        search = re.search(pat_str, cmdRes.stdout_text.strip())
        if not search:
            raise exceptions.TestFail("Pattern '%s' is not matched in "
                                      "'%s'" % (pat_str,
                                                cmdRes.stdout_text.strip()))
        else:
            return port_to_check
    else:
        pat_str = r'.*%s:(\d*).*ESTABLISHED.*qemu-kvm.*' % server_ip
        search = re.search(pat_str, cmdRes.stdout_text.strip())
        if search:
            logging.debug("Get the port used:%s", search.group(1))
            return search.group(1)
        else:
            raise exceptions.TestFail("Pattern '%s' is not matched in "
                                      "'%s'" % (pat_str,
                                                cmdRes.stdout_text.strip()))
