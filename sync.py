# https://github.com/ivanovrvl/sync

import os
import sys
import hashlib
import zipfile
import json
import shutil

HASHES_FILE_NAME = '.hashes.json'
SYNC_FILTERS_FILE = 'sync_filters.py'

ex_folder_filter = None
ex_file_filter = None

def folder_filter(parents:[str], folder:str):
    if ex_folder_filter:
        res = ex_folder_filter(parents, folder)
        if res is not None:
            return res
    if folder == '.git': return False
    if folder == '.vscode': return False
    if folder == '__pycache__': return False
    return True

# 0 - ignore always
# 1 - don`t include if exists
# 2 - don`t ignore
def file_filter(parents:[str], file:str):
    #if file==HASHES_FILE_NAME and len(parents)==0: return 0
    if file==HASHES_FILE_NAME: return 0
    if ex_file_filter:
        res = ex_file_filter(parents, file)
        if res is not None:
            return res
    if file.endswith('.log'): return 0
    if file.endswith('.bak'): return 0
    return 2

cmd = sys.argv[1]
if cmd != 'hash' or len(sys.argv)<=3 or sys.argv[3].upper() in ('1', 'TRUE', 'YES', 'T', 'Y'):
    filters_file = os.path.join(sys.argv[2], SYNC_FILTERS_FILE)
    if os.path.isfile(filters_file):
        sys.path.insert(0, sys.argv[2])
        try:
            from sync_filters import folder_filter as ex_folder_filter, file_filter as ex_file_filter
            print('Filters loaded from: ' + filters_file)
        except Exception as e:
            raise Exception('Filters load error:' + str(e))

class AbstractFsProvider:

    def __init__(self, root_folder:str):
        self.root_folder = root_folder
        self.relative_folder = []

    def get_relative_folder(self):
        return self.relative_folder

    def set_relative_folder(self, folder:[str]):
        self.relative_folder = folder

    def enter_folder(self, folder:str):
        self.relative_folder += [folder]

    def leave_folder(self):
        self.relative_folder = self.relative_folder[:-1]

    def list(self, files:bool=True, folders:bool=True):
        raise NotImplementedError()

    def upload(self, file:str, data_gen):
        raise NotImplementedError()

    def get_local_file(self, file:str):
        raise NotImplementedError()

    def put_file(self, local_file:str, file:str):
        raise NotImplementedError()

    def download(self, file:str):
        raise NotImplementedError()

    def make_folder(self, folder:str):
        raise NotImplementedError()

    def delete_file(self, file:str):
        raise NotImplementedError()

    def delete_folder(self, folder:str):
        raise NotImplementedError()

    def get_file_hash(self, file:str):
        m = hashlib.sha256()
        for b in self.download(file):
            m.update(b)
        return m.hexdigest()

    def set_file_hash(self, file:str, hash:str):
        raise NotImplementedError()

    def set_ignore_changes(self, file:str, ignore:bool):
        raise NotImplementedError()

    def get_ignore_changes(self, file:str)->bool:
        raise NotImplementedError()

    def close(self):
        pass

class ZipFsProvider(AbstractFsProvider):

    def __init__(self, zip_file_name:str):
        #self.zip_file_name = zip_file_name
        super().__init__(zip_file_name)
        self.zip = zipfile.ZipFile(zip_file_name, mode='w', compression=zipfile.ZIP_DEFLATED)
        self.file_count = 0

    def close(self):
        self.zip.close()

    def put_file(self, local_file:str, file:str):
        self.zip.write(local_file, arcname=file)
        self.file_count += 1

    def make_folder(self, folder:str):
        pass

class VirtualFsProvider(AbstractFsProvider):

    def __init__(self):
        super().__init__('')
        self.data = {}
        self.cur = [self.data]

    def _get_current(self):
        return self.cur[len(self.cur)-1]

    def _get_d_(self)->{}:
        c = self._get_current()
        d = c.get('D')
        if d is None:
            d = {}
            c['D']=d
        return d

    def _get_f_(self)->{}:
        c = self._get_current()
        d = c.get('F')
        if d is None:
            d = {}
            c['F']=d
        return d

    def make_folder(self, folder:str):
        d = self._get_d_()
        d[folder] = {}

    def enter_folder(self, folder:str):
        d = self._get_d_()
        res = d[folder]
        self.cur += [res]
        super().enter_folder(folder)
        return res

    def leave_folder(self):
        self.cur = self.cur[:-1]
        super().leave_folder()

    def list(self, files:bool=True, folders:bool=True):
        if folders:
            d = self._get_current().get('D')
            if d is not None:
                for name, _ in d.items():
                    yield name, True
        if files:
            f = self._get_current().get('F')
            if f is not None:
                for name, _ in f.items():
                    yield name, False

    def get_file_hash(self, file:str):
        f = self._get_f_().get(file)
        if f is None:
            return None
        return f['sha256']

    def set_file_hash(self, file:str, hash:str):
        f = self._get_f_()
        d = f.get(file)
        if d is None:
            f[file] = {'sha256': hash}
        else:
            d['sha256'] = hash

    def set_ignore_changes(self, file:str, ignore:bool):
        f = self._get_f_()
        d = f.get(file)
        if d is None:
            f[file] = {'ignore_changes': ignore}
        else:
            d['ignore_changes'] = ignore

    def get_ignore_changes(self, file:str)->bool:
        v = self._get_f_()[file].get('ignore_changes')
        if v is None: return False
        return True

    def save(self, file_name:str):
        with open(file_name, "w", encoding='utf8') as f:
            #json.dump(self.data, f, indent=4, sort_keys=True, ensure_ascii=False)
            json.dump(self.data, f, sort_keys=True, ensure_ascii=False)

    def load(self, file_name:str):
        with open(file_name, "r", encoding='utf8') as f:
            self.data = json.load(f)
        self.cur = [self.data]
        self.relative_folder = []

class LocalFsProvider(AbstractFsProvider):

    def list(self, files:bool=True, folders:bool=True):
        for d in os.scandir(path=os.path.join(self.root_folder, *self.relative_folder)):
            if d.is_dir():
                if folders:
                    yield d.name, True
            else:
                if files:
                    yield d.name, False

    def upload(self, file:str, data_gen):
        with open(os.path.join(self.root_folder, *self.relative_folder, file), mode='wb') as f:
            for b in data_gen:
                f.write(b)

    def download(self, file:str):
        with open(os.path.join(self.root_folder, *self.relative_folder, file), mode='rb') as f:
            while True:
                b = f.read(1024*4)
                if len(b)==0: break
                yield b

    def delete_file(self, file:str):
        os.remove(os.path.join(self.root_folder, *self.relative_folder, file))

    def delete_folder(self, folder:str):
        f = os.path.join(self.root_folder, *self.relative_folder, folder)
        shutil.rmtree(f)

    def get_local_file(self, file:str):
        return os.path.join(self.root_folder, *self.relative_folder, file)
    
    def make_folder(self, folder:str):
        path = os.path.join(self.root_folder, *self.relative_folder, folder)
        os.mkdir(path)

def calc_hashes(src_fs: AbstractFsProvider, dst_fs: VirtualFsProvider):
    level = 0
    def _calc_hashes_():
        nonlocal level
        dirs = []
        for name, is_dir in src_fs.list():
            if is_dir:
                if folder_filter(src_fs.relative_folder, name):
                    dirs.append(name)
            else:
                v = file_filter(src_fs.relative_folder, name)
                if v != 0:
                    try:
                        dst_fs.set_file_hash(name, src_fs.get_file_hash(name))
                        if v == 1:
                            dst_fs.set_ignore_changes(name, True)
                    except Exception as e:
                        print(os.path.join(*src_fs.relative_folder, name))
                        raise e
        dst_dirs = set([name for name, is_dir in dst_fs.list(files=False)])
        for d in dirs:
            if d not in dst_dirs:
                dst_fs.make_folder(d)
            src_fs.enter_folder(d)
            dst_fs.enter_folder(d)
            level += 1
            _calc_hashes_()
            level -= 1
            src_fs.leave_folder()
            dst_fs.leave_folder()
    _calc_hashes_()

def check_hashes(src_fs: VirtualFsProvider, dst_fs: AbstractFsProvider, delete:bool=True, create_folder:bool=False):
    level = 0
    def _check_hashes_():
        nonlocal  level
        dirs = []
        dst_files = set([name for name, is_dir in dst_fs.list(folders=False)])
        for name, is_dir in src_fs.list():
            if is_dir:
                if folder_filter(src_fs.relative_folder, name):
                    dirs.append(name)
            else:
                v = file_filter(src_fs.relative_folder, name)
                if v == 0:
                    if name in dst_files:
                        dst_files.remove(name)
                else:
                    try:
                        if name not in dst_files:
                            raise Exception("File not found")
                        dst_files.remove(name)
                        h1 = src_fs.get_file_hash(name)
                        h2 = dst_fs.get_file_hash(name)
                        if h1 != h2:
                            if src_fs.get_ignore_changes(name):
                                print(f"Change ignored: {os.path.join(*src_fs.relative_folder, name)}")
                            else:
                                raise Exception("Hash is different")
                    except Exception as e:
                        print(os.path.join(*src_fs.relative_folder, name))
                        raise e

        for name in dst_files:
            v = file_filter(src_fs.relative_folder, name)
            if v != 0:
                try:
                    if delete:
                        print(f"Deleting file: {os.path.join(*src_fs.relative_folder, name)}")
                        dst_fs.delete_file(name)
                    else:
                        raise Exception("Redundant file")
                except Exception as e:
                    print(os.path.join(*src_fs.relative_folder, name))
                    raise e

        dst_dirs = set([name for name, is_dir in dst_fs.list(files=False)])
        for name in dirs:
            try:
                if name not in dst_dirs:
                    if create_folder:
                        print(f"Creating folder: {os.path.join(*dst_fs.relative_folder, name)}")
                        dst_fs.make_folder(name)
                    else:
                        raise Exception(f"Folder not found")
                else:
                    dst_dirs.remove(name)
            except Exception as e:
                print(os.path.join(*src_fs.relative_folder, name))
                raise e
            src_fs.enter_folder(name)
            dst_fs.enter_folder(name)
            level += 1
            _check_hashes_()
            level -= 1
            src_fs.leave_folder()
            dst_fs.leave_folder()

        for name in dst_dirs:
            if folder_filter(dst_fs.relative_folder, name):
                try:
                    if delete:
                        print(f"Deleting folder: {os.path.join(*dst_fs.relative_folder, name)}")
                        dst_fs.delete_folder(name)
                    else:
                        raise Exception("Redundant folder")
                except Exception as e:
                    print(os.path.join(*src_fs.relative_folder, name))
                    raise e

    _check_hashes_()

def extract_delta(src_fs: AbstractFsProvider, src_hashes: VirtualFsProvider, delta: AbstractFsProvider, hashes: VirtualFsProvider, dont_recalc_src_hashes:bool):
    level = 0

    def _extract_delta(skip_src2:bool=False):
        nonlocal  level, hashes
        dirs = []
        if skip_src2:
            src2_files = set()
        else:
            src2_files = set([name for name, is_dir in src_hashes.list(folders=False)])
        for name, is_dir in src_fs.list():
            if is_dir:
                if folder_filter(src_fs.relative_folder, name):
                    dirs.append(name)
            else:
                v = file_filter(src_fs.relative_folder, name)
                if v != 0:
                    try:
                        if dont_recalc_src_hashes:
                            h1 = hashes.get_file_hash(name)
                            if h1 is None:
                                raise Exception("File hash not found")
                        else:
                            h1 = src_fs.get_file_hash(name)
                            hashes.set_file_hash(name, h1)
                        if v == 1:
                            hashes.set_ignore_changes(name, True)
                        sync = name not in src2_files
                        if not sync:
                            h2 = src_hashes.get_file_hash(name)
                            if h1 != h2:
                                if v == 1:
                                    print(f"Change ignored: {os.path.join(*src_fs.relative_folder, name)}")
                                else:
                                    sync = True
                        if sync:
                            delta.put_file(src_fs.get_local_file(name), os.path.join(*delta.relative_folder, name))
                    except Exception as e:
                        print(os.path.join(*src_fs.relative_folder, name))
                        raise e
        if skip_src2:
            src2_dirs = set()
        else:
            src2_dirs = set([name for name, is_dir in src_hashes.list(files=False)])
        for name in dirs:
            try:
                delta.make_folder(name)
                if not dont_recalc_src_hashes:
                    hashes.make_folder(name)
            except Exception as e:
                print(os.path.join(*src_fs.relative_folder, name))
                raise e
            src_fs.enter_folder(name)
            delta.enter_folder(name)
            hashes.enter_folder(name)
            level += 1
            if name in src2_dirs:
                src_hashes.enter_folder(name)
                _extract_delta(False)
                src_hashes.leave_folder()
            else:
                _extract_delta(True)
            level -= 1
            src_fs.leave_folder()
            hashes.leave_folder()
            delta.leave_folder()

    _extract_delta(False)

def do_calc_hashes(root_dir):
    p  = LocalFsProvider(root_dir)
    v = VirtualFsProvider()
    calc_hashes(p, v)
    v.save(os.path.join(root_dir, HASHES_FILE_NAME))
    v.close()
    p.close()

def do_check_hashes(root_dir, delete:bool=False, create_folder:bool=False):
    p  = LocalFsProvider(root_dir)
    v = VirtualFsProvider()
    v.load(os.path.join(root_dir, HASHES_FILE_NAME))
    check_hashes(v, p, delete=delete, create_folder=create_folder)
    v.close()
    p.close()

def do_extract_delta(root_dir, hashes_file:str, delta_file:str, dont_recalc_src_hashes:bool=False):
    p  = LocalFsProvider(root_dir)
    v = VirtualFsProvider()
    hashes = VirtualFsProvider()
    z = ZipFsProvider(delta_file)
    if not(hashes_file is None or hashes_file.strip()==''):
        v.load(hashes_file)
    hash_file = os.path.join(root_dir, HASHES_FILE_NAME)
    if dont_recalc_src_hashes:
        hashes.load(hash_file)
    extract_delta(p, v, z, hashes, dont_recalc_src_hashes=dont_recalc_src_hashes)    
    if not dont_recalc_src_hashes:
        hashes.save(hash_file)
    file_count = z.file_count
    z.put_file(hash_file, HASHES_FILE_NAME)
    v.close()
    hashes.close()
    p.close()
    z.close()
    return file_count

def print_help():
    print("One of:")
    print("  hash <folder> [<use filters (true/false) default true>]")
    print("  check <folder>")
    print("  final <folder>")
    print("  delta <folder> <hashes file> <output file>")

if __name__ == '__main__':

    n = len(sys.argv)
    if n < 3:
        print_help()
        sys.exit(2)    
    try:
        if cmd == 'hash' and n in (3, 4):
            do_calc_hashes(sys.argv[2])
        elif cmd == 'check' and n == 3:
            do_check_hashes(sys.argv[2])
        elif cmd == 'final' and n == 3:
            do_check_hashes(sys.argv[2], delete=True, create_folder=True)
        elif cmd in ('delta', 'delta2') and n == 5:
            file_count = do_extract_delta(sys.argv[2], sys.argv[3], sys.argv[4], dont_recalc_src_hashes=(cmd=='delta2'))
            print(f"{file_count} files added")
            if file_count == 0:
                sys.exit(1)                
        else:
            print_help()
            sys.exit(2)
    except Exception as e:
        print(f"ERROR: {str(e)}")
        sys.exit(2)