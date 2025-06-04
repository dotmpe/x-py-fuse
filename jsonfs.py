import argparse
import base64
import errno
import json
import logging
import os
import stat
import sys

from datetime import datetime
from fuse import FUSE, FuseOSError, LoggingMixIn, Operations
from fs.permissions import Permissions


perm_strs = ['---', '--x', '-w-', '-wx', 'r--', 'r-x', 'rw-', 'rwx']


def mode_typemask(mode):
    "Mask out the file type bits to get only permissions (last 9 bits)"

    return mode & ~stat.S_IFMT(mode)


def mode_to_permissions(mode):
    "Extract owner, group, other permissions from mode and string format"

    owner = perm_strs[(mode >> 6) & 0o7]
    group = perm_strs[(mode >> 3) & 0o7]
    other = perm_strs[mode & 0o7]

    return f"{owner}{group}{other}"


class FSObjectStoreA(object): pass


class FSObjectStoreB(object):

    builtins = {
        '.vfs': {
            'entries': {
                'fsobj.json': {
                    'cb': '_dump_json',
                    'permissions': 'rw-rw-rw-'
                },
            },
            'permissions': 'r--r--r--'
        }
    }

    def __init__(self, data):
        self.fs = data
        self.changed = False

    def find_base(self, path):
        node = self.fs
        _path = []
        for part in path.strip('/').split('/'):
            if not part:
                continue
            if part not in node['entries']:
                break
            _path.append(part)
            node = node['entries'][part]
        return '/'+('/'.join(_path)), node

    def get_path(self, node):
        pass

    def put_leaf(self, path, data, **attr):
        pass

    def put_node(self, path, **attr):
        base_path, parent = self.find_base(path)
        print(f"Put at {path}: {base_path}: {parent}")

    def get_builtin(self, path):
        return self._get_node({'entries':self.builtins}, path)

    def get_node(self, path):
        return self._get_node(self.fs, path)

    def _dump_json(self):
        return json.dumps(self.fs)

    def _get_node(self, store, path):
        node = store
        for part in path.strip('/').split('/'):
            if not part:
                continue
            node = node['entries'][part]
        return node


class NodeFS(Operations):

    """
    A barely minimal read-only filesystem working directly from a dict.
    """

    def __init__(self, store):
        super(NodeFS, self).__init__()
        self.store = store
        print(self.store)

    def get_node(self, path):
        try:
            return self.store.get_node(path)
        except:
            try:
                return self.store.get_builtin(path)
            except:
                raise FuseOSError(errno.ENOENT)

    def access(self, path, amode):
        if amode & os.F_OK or amode & os.R_OK:
            try:
                self.store.get_node(path)
            except:
                raise FuseOSError(errno.ENOENT)
        elif amode & os.W_OK:
            raise FuseOSError(errno.ENOTSUP)
        elif amode & os.X_OK:
            raise FuseOSError(errno.ENOTSUP)
        return 0

    def chmod(self, path, mode):
        return super(NodeFS, self).chmod(path, mode)
        #raise FuseOSError(errno.ENOTSUP)

    def chown(self, path, uid, gid):
        return super(NodeFS, self).chown(path, uid, gid)
        #raise FuseOSError(errno.ENOTSUP)

    def create(self, path, mode, fi=None):
        #node = self.store.get_node(path)
        #full_path = self._full_path(path)
        #return os.open(full_path, os.O_WRONLY | os.O_CREAT, mode)
        #raise FuseOSError(errno.ENOTSUP)
        return super(NodeFS, self).create(path, mode, fi)

    def destroy(self, path):
        return super(NodeFS, self).destroy(path)

    def flush(self, path, fh):
        return super(NodeFS, self).flush(path, fh)

    def fsync(self, path, datasync, fh):
        return super(NodeFS, self).fsync(path, datasync, fh)

    def fsyncdir(self, path, datasync, fh):
        return super(NodeFS, self).fsyncdir(path, datasync, fh)

    def getattr(self, path, fh=None):
        node = self.get_node(path)
        target = node.get('target', None)
        dt = datetime.timestamp(datetime.now())
        st = dict(
            st_atime = dt,
            st_mtime = dt,
            st_ctime = dt,
            st_uid = 1000,
            st_gid = 1000
        )
        perm_str = node.get('permissions', None)
        if perm_str:
            pmode = Permissions.parse(perm_str).mode
        else:
            pmode = (target or 'data' in node) and 0o644 or 0o755
        if 'cb' in node:
            st.update(dict(
                st_mode = stat.S_IFCHR | pmode,
                st_size = 0,
                st_nlink = 1
            ))
            return st
        if target:
            st.update(dict(
                st_mode = stat.S_IFLNK | pmode,
                st_nlink = 1
            ))
        elif node.get('data', None):
            st.update(dict(
                st_mode = stat.S_IFREG | pmode,
                st_size = node.get('size', 0),
                st_nlink = 1
            ))
        else:
            st['st_mode'] = stat.S_IFDIR | pmode
            st['st_nlink'] = 2
        return st

    def getxattr(self, path, name, position=0):
        return super(NodeFS, self).getxattr(path, name, position=0)

    def init(self, path):
        return super(NodeFS, self).init(path)

    def ioctl(self, path, cmd, arg, fip, flags, data):
        return super(NodeFS, self).ioctl(path, cmd, arg, fip, flags, data)

    def link(self, target, source):
        return super(NodeFS, self).link(target, source)

    def listxattr(self, path):
        return super(NodeFS, self).listxattr(path)

    def mkdir(self, path, mode):
        #self.store.put_node(path, permissions=str(p))
        node = self.store.fs
        path = path.strip('/').split('/')
        for part in path[:-1]:
            if not part:
                continue
            if part not in node['entries']:
                raise FuseOSError(errno.ENOENT)
            node = node['entries'][part]
        node['entries'][path[-1]] = dict(
            permissions=mode_to_permissions(mode),
            entries={}
        )

    def mknod(self, path, mode, dev):
        raise FuseOSError(errno.ENOTSUP)

    def open(self, path, flags):
        return super(NodeFS, self).open(path, flags)
        #raise FuseOSError(errno.ENOTSUP)
        #node = self.store.get_node(path)
    #    access_flags = os.O_RDONLY | os.O_WRONLY | os.O_RDWR
    #    if flags & access_flags != os.O_RDONLY:
    #        return -errno.EACCES
    #    else:
    #        return 0

    def opendir(self, path):
        return super(NodeFS, self).opendir(path)

    def read(self, path, size, offset, fh):
        node = self.get_node(path)
        if not node.get('data', None):
            cb = node.get('cb', None)
            if cb:
                data = getattr(self.store, cb)()
                s = len(data)
                print(f"Getting data {s}: {data}")
                return data
            raise OSError(errno.EISDIR, path)
        encoding = node.get('encoding', 'text')
        if encoding == 'text':
            data = node['data'].encode()
        elif encoding == 'base64':
            data = base64.b64decode(node['data'])
        else:
            return ''
        return data[offset:offset + size]

    def readdir(self, path, offset):
        node = self.get_node(path)
        if node.get('data', None):
            raise OSError(errno.ENOTDIR, path)
        return ['.', '..'] + list(node['entries'].keys())

    def readlink(self, path):
        #node = self.get_node(path)
        node = self.store.get_node(path)
        target = node.get('target', None)
        if not target:
            raise OSError(errno.ENOLINK, path)
        return target

    def release(self, path, fh):
        return super(NodeFS, self).release(path, fh)

    def releasedir(self, path, fh):
        return super(NodeFS, self).releasedir(path, fh)

    def removexattr(self, path, name):
        return super(NodeFS, self).removexattr(path, name)

    def rename(self, old, new):
        return super(NodeFS, self).rename(old, new)

    def rmdir(self, path):
        raise FuseOSError(errno.ENOTSUP)

    def setxattr(self, path, name, value, options, position=0):
        return super(NodeFS, self).setxattr(path, name, value, options, position=0)

    def statfs(self, path):
        raise FuseOSError(errno.ENOTSUP)

    def symlink(self, target, source):
        return super(NodeFS, self).symlink(target, source)

    def truncate(self, path, length, fh=None):
        raise FuseOSError(errno.ENOTSUP)

    def utimens(self, path, times=None):
        raise FuseOSError(errno.ENOTSUP)

    def write(self, path, buf, offset, fh):
        raise FuseOSError(errno.ENOTSUP)


class DebugNodeFS(LoggingMixIn, NodeFS): pass


def parse_args():
    parser = argparse.ArgumentParser(
            description="Synthetic filesystem with in-memory backend loaded fromJSON")

    parser.add_argument("-d", "--debug", action="store_true",
            help="Enable debug logging")

    parser.add_argument("-L", "--log-file", action="store_true",
            help="Set log file (default: %(log_file)s)")
    parser.add_argument("-s", "--stderr", action="store_true",
            help="Enable logging to standard error")
    parser.add_argument("-S", "--syslog", action="store_true",
            help="Enable logging to system")
    parser.add_argument("--log-level", default=os.getenv("LOG_LEVEL", "ERROR"),
            help="Set log level (DEBUG, INFO, WARNING, ERROR, CRITICAL; default, via env LOG_LEVEL: %(default)s)")

    parser.add_argument("json_path", default='fs.json', nargs='?',
            help="JSON file backend (default: %(default)s)")
    parser.add_argument("mount_point", default='/mnt/jsonfs', nargs='?',
            help="Mount point for the filesystem (default: %(default)s)")
    return parser.parse_args()


def setup_logging(output=None, log_file='fs.log', threshold_level='ERROR',
        syslog=False):

    """
    Setup pythong logging library. Note: to get LoggingMixIn events, threshold
    must be at DEBUG.
    """

    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }
    log_level = level_map[threshold_level.upper()]

    # Custom formatter to include PID and process name
    class CustomFormatter(logging.Formatter):
        def format(self, record):
            # Add PID and process name to the log record
            record.pid = os.getpid()
            try:
                record.process_name = psutil.Process(record.pid).name()
            except psutil.NoSuchProcess:
                record.process_name = "unknown"
            return super().format(record)

    formatter = CustomFormatter(
        "%(asctime)s [%(levelname)s] [PID:%(pid)s/%(process_name)s] %(message)s"
    )
    handlers = [
        logging.FileHandler(log_file)
    ]
    if output:
        handlers.append(logging.StreamHandler(output))
    if syslog:
        handlers.append(logging.handlers.SysLogHandler('/dev/log'))
    for handler in handlers:
        handler.setFormatter(formatter)
    logging.basicConfig(level=log_level, handlers=handlers)


if __name__ == '__main__':
    args = parse_args()
    if not os.path.isdir(args.mount_point):
        raise Exception(f"No such directory {args.mount_point}")
    with open(args.json_path, 'r') as f:
        store = FSObjectStoreB(json.load(f))
    if args.debug:
        setup_logging()
        fs_class = DebugNodeFS
    else:
        fs_class = NodeFS
    FUSE(fs_class(store), args.mount_point,
            nothreads=True,
            foreground=True,
            direct_io=True)
