import importlib, inspect
m = importlib.import_module('securesystemslib.interface')
print('pub import sig:', inspect.signature(m.import_publickey_from_file))
