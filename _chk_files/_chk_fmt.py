import importlib
fmt = importlib.import_module('securesystemslib.formats')
print('has encode_canonical?', hasattr(fmt, 'encode_canonical'))
