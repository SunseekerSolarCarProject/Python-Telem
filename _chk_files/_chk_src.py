import inspect, importlib
ssi = importlib.import_module('securesystemslib.interface')
print(ssi.import_publickeys_from_file.__doc__)
print('---SOURCE START---')
print(inspect.getsource(ssi.import_publickeys_from_file))
