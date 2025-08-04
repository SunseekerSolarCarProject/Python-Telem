import sys
import importlib
import importlib.metadata

# map the module you import → the PyPI/distribution name
MODULES = {
    "sys":           None,            # stdlib → report sys.version
    "os":            None,            # stdlib
    "logging":       None,            # stdlib
    "json":          None,            # stdlib
    "shutil":        None,            # stdlib
    "requests":      "requests",
    "joblib":        "joblib",
    "pandas":        "pandas",
    "sklearn":       "scikit-learn",
    "dotenv":        "python-dotenv",
    "numpy":         "numpy",
    "serial":        "pyserial",
    "pyqtgraph":     "pyqtgraph",
    "tufup":         "tufup",
    "PyQt6.QtWidgets":"PyQt6"
}

for module_name, dist_name in MODULES.items():
    try:
        if dist_name:
            # look up in package metadata
            version = importlib.metadata.version(dist_name)
        else:
            # standard‐lib → use Python version
            version = sys.version.split()[0]
    except importlib.metadata.PackageNotFoundError:
        # fallback to module.__version__ if present
        try:
            mod = importlib.import_module(module_name)
            version = getattr(mod, "__version__", "unknown")
        except ImportError:
            version = "not installed"
    print(f"{module_name:20s} {version}")
