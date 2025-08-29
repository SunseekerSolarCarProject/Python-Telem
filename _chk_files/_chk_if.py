import importlib, inspect
ssi = importlib.import_module('securesystemslib.interface')
print([n for n in dir(ssi) if 'sign' in n or 'canonical' in n or 'metadata' in n])
