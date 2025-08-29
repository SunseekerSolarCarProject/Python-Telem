import importlib, inspect
keys = importlib.import_module('securesystemslib.keys')
print('keys functions:', [n for n in dir(keys) if 'sign' in n or 'create_' in n or 'import' in n or 'format' in n])
