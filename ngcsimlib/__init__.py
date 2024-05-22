from . import utils
from . import controller
from . import commands

import argparse, os, warnings, json
from types import SimpleNamespace
from importlib import import_module
from ngcsimlib.configManager import init_config, get_config

from pkg_resources import get_distribution

__version__ = get_distribution('ngcsimlib').version  ## set software version


###### Preload Modules
def preload_modules():
    module_config = get_config("modules")
    if module_config is None:
        module_path = "json_files/modules.json"
    else:
        module_path = module_config.get("module_path", "json_files/modules.json")

    if not os.path.isfile(module_path):
        warnings.warn("\nMissing file to preload modules from. Attempted to locate file at \"" + str(module_path) +
                      "\". No modules will be preloaded. "
                      "\nSee https://ngc-learn.readthedocs.io/en/latest/tutorials/model_basics/json_modules.html for additional information")
        return

    with open(module_path, 'r') as file:
        modules = json.load(file, object_hook=lambda d: SimpleNamespace(**d))

    for module in modules:
        mod = import_module(module.absolute_path)
        utils._Loaded_Modules[module.absolute_path] = mod

        for attribute in module.attributes:
            atr = getattr(mod, attribute.name)
            utils._Loaded_Attributes[attribute.name] = atr

            utils._Loaded_Attributes[".".join([module.absolute_path, attribute.name])] = atr
            if hasattr(attribute, "keywords"):
                for keyword in attribute.keywords:
                    utils._Loaded_Attributes[keyword] = atr


###### Initialize Config
def configure():
    parser = argparse.ArgumentParser(description='Build and run a model using ngclearn')
    parser.add_argument("--config", type=str, help='location of config.json file')

    ## ngc-sim-lib only cares about --config argument
    args, unknown = parser.parse_known_args()  # args = parser.parse_args()
    try:
        config_path = args.modules
    except:
        config_path = None

    if config_path is None:
        config_path = "json_files/config.json"

    if not os.path.isfile(config_path):
        warnings.warn("\nMissing configuration file. Attempted to locate file at \"" + str(config_path) +
                      "\". Default Config will be used. "
                      "\nSee https://ngc-learn.readthedocs.io/en/latest/tutorials/model_basics/configuration.html for "
                      "additional information")
        return


    init_config(config_path)



