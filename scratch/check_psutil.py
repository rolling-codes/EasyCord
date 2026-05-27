from importlib.util import find_spec

if find_spec("psutil") is not None:
    print("psutil is installed")
else:
    print("psutil is NOT installed")
