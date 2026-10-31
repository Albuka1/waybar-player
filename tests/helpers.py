from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, relative_path):
    path = ROOT / relative_path
    loader = SourceFileLoader(name, str(path))
    spec = spec_from_loader(name, loader)
    module = module_from_spec(spec)
    loader.exec_module(module)
    return module
