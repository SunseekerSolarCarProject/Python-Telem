import importlib, inspect
keys = importlib.import_module('securesystemslib.keys')
print('create_signature sig:', inspect.signature(keys.create_signature))
print(keys.create_signature.__doc__)
