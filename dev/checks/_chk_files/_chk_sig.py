import importlib, inspect
try:
    m = importlib.import_module('securesystemslib.interface')
    print('OK')
    print('ed25519:', inspect.signature(m.generate_and_write_ed25519_keypair))
except Exception as e:
    print('ERR:', e)
