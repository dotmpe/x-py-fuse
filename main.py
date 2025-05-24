import errno
import json
import os
import stat
import sys
import base64
from datetime import datetime
from fuse import FUSE, Operations, FuseOSError

class FSObjectStoreA(object): pass

class FSObjectStoreB(object):
    def __init__(self, data):
        self.fs = data

    def get_node(self, path):
        node = self.fs
        for part in path.strip('/').split('/'):
            if not part:
                continue
            node = node['contents'][part]
        return node

class NodeFS(Operations):
    """
    A barely minimal read-only filesystem working directly from a dict.
    """
    def __init__(self, store):
        super(NodeFS, self).__init__()
        self.store = store

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

    def getattr(self, path, fh=None):
        print(f"GetAttr {path} fh {fh}")
        try:
            node = self.store.get_node(path)
        except:
            return {}
        target = node.get('target', None)
        dt = datetime.timestamp(datetime.now())
        st = dict(
            st_atime = dt,
            st_mtime = dt,
            st_ctime = dt,
            st_uid = 1000,
            st_gid = 1000
        )
        if target:
            st.update(dict(
                st_mode = stat.S_IFLNK | 0o644,
                st_nlink = 1
            ))
        elif node.get('data', None):
            st.update(dict(
                st_mode = stat.S_IFREG | 0o644,
                st_size = node.get('size', 0),
                st_nlink = 1
            ))
        else:
            st['st_mode'] = stat.S_IFDIR | 0o755
            st['st_nlink'] = 2
        return st

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

    def read(self, path, size, offset, fh):
        node = self.store.get_node(path)
        print(f"Read path {path} {size} {offset} {fh}")
        if not node.get('data', None):
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
        node = self.store.get_node(path)
        print(f"Read dir {path} {offset}")
        if node.get('data', None):
            raise OSError(errno.ENOTDIR, path)
        return ['.', '..'] + list(node['contents'].keys())

    def readlink(self, path):
        node = self.store.get_node(path)
        target = node.get('target', None)
        if not target:
            raise OSError(errno.ENOLINK, path)
        return target

    def rmdir(self, path):
        print(f"RmDir {path}")
        raise FuseOSError(errno.ENOTSUP)

    def mkdir(self, path, mode):
        print(f"MkDir {path} mode {mode}")
        raise FuseOSError(errno.ENOTSUP)

    def statfs(self, path):
        print(f"StatFs {path}")
        raise FuseOSError(errno.ENOTSUP)

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
    FUSE(NodeFS(store), mnt_point, nothreads=True, foreground=True)
