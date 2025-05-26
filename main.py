import errno
import json
import os
import stat
import sys
import base64
from datetime import datetime
from fuse import FUSE, Operations, FuseOSError
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

    def get_node(self, path):
        try:
            return self.store.get_node(path)
        except:
            try:
                return self.store.get_builtin(path)
            except:
                raise FuseOSError(errno.ENOENT)

    def access(self, path, amode):
        print(f"Access {path}, {amode}")
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
        print(f"Chmod {path}, {mode}")
        return super(NodeFS, self).chmod(path, mode)
        #raise FuseOSError(errno.ENOTSUP)

    def chown(self, path, uid, gid):
        print(f"Chown {path}, {uid}, {gid}")
        return super(NodeFS, self).chown(path, uid, gid)
        #raise FuseOSError(errno.ENOTSUP)

    def create(self, path, mode, fi=None):
        print(f"Create {path} mode {mode} fi {fi}")
        #node = self.store.get_node(path)
        #full_path = self._full_path(path)
        #return os.open(full_path, os.O_WRONLY | os.O_CREAT, mode)
        #raise FuseOSError(errno.ENOTSUP)
        return super(NodeFS, self).create(path, mode, fi)

    def destroy(self, path):
        print(f"destroy {path}")
        return super(NodeFS, self).destroy(path)

    def flush(self, path, fh):
        print(f"flush {path}")
        return super(NodeFS, self).flush(path, fh)

    def fsync(self, path, datasync, fh):
        print(f"fsync {path}")
        return super(NodeFS, self).fsync(path, datasync, fh)

    def fsyncdir(self, path, datasync, fh):
        print(f"fsyncdir {path}")
        return super(NodeFS, self).fsyncdir(path, datasync, fh)

    def getattr(self, path, fh=None):
        print(f"GetAttr {path} fh {fh}")
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
        print(f"getxattr {path} {name} {position}")
        return super(NodeFS, self).getxattr(path, name, position=0)

    def init(self, path):
        print(f"init {path}")
        return super(NodeFS, self).init(path)

    def ioctl(self, path, cmd, arg, fip, flags, data):
        print(f"ioctl {path}")
        return super(NodeFS, self).ioctl(path, cmd, arg, fip, flags, data)

    def link(self, target, source):
        print(f"link {target} {source}")
        return super(NodeFS, self).link(target, source)

    def listxattr(self, path):
        print(f"listxattr {path}")
        return super(NodeFS, self).listxattr(path)

    def mkdir(self, path, mode):
        print(f"MkDir {path} mode {mode}")
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
        print(f"MkNod {path} mode {mode} dev {dev}")
        raise FuseOSError(errno.ENOTSUP)

    def open(self, path, flags):
        print(f"Open {path} flags {flags}")
        return super(NodeFS, self).open(path, flags)
        #raise FuseOSError(errno.ENOTSUP)
        #node = self.store.get_node(path)
    #    access_flags = os.O_RDONLY | os.O_WRONLY | os.O_RDWR
    #    if flags & access_flags != os.O_RDONLY:
    #        return -errno.EACCES
    #    else:
    #        return 0

    def opendir(self, path):
        print(f"opendir {path}")
        return super(NodeFS, self).opendir(path)

    def read(self, path, size, offset, fh):
        node = self.get_node(path)
        print(f"Read path {path} {size} {offset} {fh}")
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
        print(f"Read dir {path} {offset}")
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
        print(f"release {path} {fh}")
        return super(NodeFS, self).release(path, fh)

    def releasedir(self, path, fh):
        print(f"releasedir {path} {fh}")
        return super(NodeFS, self).releasedir(path, fh)

    def removexattr(self, path, name):
        print(f"removexattr {path} {name}")
        return super(NodeFS, self).removexattr(path, name)

    def rename(self, old, new):
        print(f"rename {old} {new}")
        return super(NodeFS, self).rename(old, new)

    def rmdir(self, path):
        print(f"RmDir {path}")
        raise FuseOSError(errno.ENOTSUP)

    def setxattr(self, path, name, value, options, position=0):
        print(f"setxattr {path} {name} {value} {options} {position}")
        return super(NodeFS, self).setxattr(path, name, value, options, position=0)

    def statfs(self, path):
        print(f"StatFs {path}")
        raise FuseOSError(errno.ENOTSUP)

    def symlink(self, target, source):
        print(f"symlink {target} {source}")
        return super(NodeFS, self).symlink(target, source)

    def truncate(self, path, length, fh=None):
        print(f"Truncate {path} length {length} fh {fh}")
        raise FuseOSError(errno.ENOTSUP)

    def utimens(self, path, times=None):
        print(f"UtimeNs {path} times {times}")
        raise FuseOSError(errno.ENOTSUP)

    def write(self, path, buf, offset, fh):
        print(f"Write {path} buf {buf} offset {offset} fh {fh}")
        raise FuseOSError(errno.ENOTSUP)

if __name__ == '__main__':
    if len(sys.argv) > 3:
        raise Exception("No more than 2 arguments expected")
    args = iter(sys.argv[1:])
    json_path = next(args, 'fs.json')
    mnt_point = next(args, '/mnt/jsonfs')
    if not os.path.isdir(mnt_point):
        raise Exception(f"No such directory {mnt_point}")
    with open(json_path, 'r') as f:
        store = FSObjectStoreB(json.load(f))
    FUSE(NodeFS(store), mnt_point, nothreads=True, foreground=True,
            direct_io=True)
