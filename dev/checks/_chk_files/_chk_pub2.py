import importlib, inspect
m = importlib.import_module('securesystemslib.interface')
print('pub import sig:', inspect.signature(m.import_publickeys_from_file))
