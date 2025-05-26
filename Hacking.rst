Using a Python virtual env (I always forget how to do this part)
::

  python3.8 -m venv .venv
  pip install -r requirements.txt


To-Do
------
- Replace current loglines with something better like a debug wrapper
  or explore FUSE debug options
- Implement hidden file to dump JSON after writing/updating
- Implement writing: files, symlinks
- Implement handles (open{,dir})
- Implement xattr

Issues
------
- tried implementing a character device for streaming or 0-size descriptor,
  could not get that to work yet

..
