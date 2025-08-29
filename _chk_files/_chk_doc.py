import importlib, inspect, textwrap
m = importlib.import_module('securesystemslib.interface')
print(textwrap.dedent(m.generate_and_write_ed25519_keypair.__doc__ or ''))
