"""
various utils functions
"""

from __future__ import print_function
import logging
import os
import shlex
import subprocess
import sys

logger = logging.getLogger(__name__)


class CmdResult(object):
    """result of a process command"""

    def __init__(self, process, returncode, out=None, err=None):
        self.process = process
        self.returncode = returncode
        self.out = out
        self.err = err

    @property
    def success(self):
        """return true if command successful """
        return self.returncode == 0

    def wait(self):
        """wait for process to finish"""
        if (self.process is not None):
            self.process.wait()
            self.returncode = self.process.returncode

    def __iter__(self):
        if not self.out:
            return
        for line in self.out.splitlines():
            yield line

    def exit_on_error(self, msg="Error"):
        if not self.success:
            print("{msg}: {err} (errno {errno})".format(
                msg=msg,errno=self.returncode, err=self.err), file=sys.stderr)
            sys.exit(1)


    def print_on_error(self, msg="Error"):
        if not self.success:
            if self.err:
                errmsg = self.err
            else:
                errmsg = self.out

            print("{msg}: {err} (errno {errno})".format(
                msg=msg,errno=self.returncode, err=errmsg), file=sys.stderr)


def cmd(a_cmd, _shell=False, _detached=False, _env=None, _cwd=None,
        _log=None, **kwargs):
    """execute a system command

    Examples

    res = cmd("cp {src} {dst}", src="/a", dst="/b")
    res = cmd("sleep 1000", _detached=True)
    res = cmd("df -h")

    res = cmd("ls -1 /bin/{filt}", filt="d*", _shell=True)
    if res.success:
       for line in res: print line
    else:
       print("Error {}: {}".format(res.returncode, res.err))

    :param cmd: string containing template to execute
    :param _shell: invoke using shell if True (Default value = False)
    :param _detached: detached process if True (Default value = False)
    :param _env: dictionary with env variables (Default value = None)
    :param _cwd: current working directory (Default value = None)
    :param _log: logger to use (Default value = None)
    :param **kwargs: template command arguments

    :return: instance of CmdResult
    """
    res = None
    cmd_fmt = None
    cmd_args = None

    if len(kwargs) > 0:
        cmd_fmt = a_cmd.format(**kwargs)
    elif isinstance(a_cmd, str):
        cmd_fmt = a_cmd
    elif isinstance(a_cmd, list):
        cmd_args = a_cmd

    if cmd_fmt:
        if _shell:
            cmd_args = cmd_fmt
        else:
            cmd_args = shlex.split(cmd_fmt)


    if _log:
        _log.debug("Executing: %s", str(cmd_args))

    try:
        if _detached:
            p = subprocess.Popen(cmd_args, shell=_shell)
            res = CmdResult(p, p.returncode)
        else:
            p = subprocess.Popen(cmd_args, shell=_shell,
                                 stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 env=_env,
                                 cwd=_cwd)
            (out, err) = p.communicate()
            res = CmdResult(p, p.returncode, out, err)
    except OSError as exc:
        res = CmdResult(process=None, returncode=exc.errno, err=exc.strerror)
        if _log:
            _log.error("Error %d: %s", exc.errno, exc.strerror)
    return res



def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller

    :param relative_path: path to concatenate with base path

    """
    try:
        # PyInstaller creates a temp folder and stores path in
        # _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.dirname(__file__))

    return os.path.join(base_path, relative_path)


def test_cmd():
    """simple test for cmd function"""
    # res = cmd("sleep 1000", _detached=True)
    res = cmd("ls -1 /bin/{filt}", filt="d*", _shell=True)
    # res = cmd("df -h")
    if res.success:
        for l in res:
            print(">>{}<<".format(l))
    else:
        print("Error {}: {}".format(res.returncode, res.err))





if __name__ == '__main__':
    test_cmd()
