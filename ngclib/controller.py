from ngclib.utils import check_attributes, load_from_path, make_unique_path, check_serializable
import json, os, warnings


class Controller:
    """
    The ngc controller is the foundation of all ngclearn models. The controller is the object that organizes all the
    components, commands, and connections for a model.
    """
    def __init__(self):
        self.steps = []
        self.commands = {}
        self.components = {}
        self.connections = []

        self._json_objects = {
            "commands": [],
            "steps": [],
            "components": [],
            "connections": []
        }

    def __getitem__(self, item):
        return self.__getattribute__(item)

    def runCycle(self, **kwargs):
        """
        Runs all the commands that have been added to a cycle in the order they were added. All keyword arguments that
        are needed to run the commands in the cycle are passed in here and will be forwarded to each command.
        :param kwargs: all keyword arguments that are needed to run every command in the cycle
        """
        for step in self.steps:
            self[step](**kwargs)

    def verify_connections(self, skip_components=None):
        """
        Loops through all components in the controller and calls the `verify_connections` method on each.
        :param skip_components: a list of component names to skip over while verifying connections (default None)
        """
        for component in self.components.keys():
            if skip_components is not None and component.name in skip_components:
                continue
            else:
                self.components[component].verify_connections()

    def connect(self, source_component_name, source_compartment_name, destination_component_name,
                target_compartment_name, bundle=None):
        """
        Creates a cable from one component to another

        :param source_component_name: the name of the component providing the value
        :param source_compartment_name: the name of the compartment containing the source value
        :param destination_component_name: the name of the component receiving the value
        :param target_compartment_name: the name of the compartment to store the source value in
        :param bundle: the number of the bundle rule to be used when using this cable (default None)
        :return:
        """
        self.components[destination_component_name].create_incoming_connection(
            self.components[source_component_name].create_outgoing_connection(source_compartment_name), target_compartment_name,
            bundle)
        self.connections.append((source_component_name, source_compartment_name, destination_component_name, target_compartment_name, bundle))
        self._json_objects['connections'].append({
            "source_component_name": source_component_name,
            "source_compartment_name": source_compartment_name,
            "target_component_name": destination_component_name,
            "target_compartment_name": target_compartment_name,
            "bundle": bundle})

    def make_connections(self, path_to_cables_file):
        """
        Loads a collection of cables from a json file. Follow `cables.schema` for the format of the json file.
        :param path_to_cables_file: the path to the file, including the name and extension
        """
        with open(path_to_cables_file, 'r') as file:
            cables = json.load(file)
            for cable in cables:
                self.connect(**cable)

    def make_components(self, path_to_components_file, custom_file_dir=None):
        """
        Loads a collection of components from a json file. Follow `components.schema` for the format of the json file.
        :param path_to_components_file: the path to the file, including the name and extension
        :param custom_file_dir: the path to the custom directory for custom load methods, this directory is named
        `custom` if the save_to_json method is used. (default None)
        """
        with open(path_to_components_file, 'r') as file:
            components = json.load(file)
            for component in components:
                self.add_component(**component, directory=custom_file_dir)

    def make_steps(self, path_to_steps_file):
        """
        Loads a collection of steps from a json file. Follow `steps.schema` for the format of this json file
        :param path_to_steps_file: the path of the file, including the name and extension
        """
        with open(path_to_steps_file, 'r') as file:
            steps = json.load(file)
            for step in steps:
                self.add_step(**step)

    def make_commands(self, path_to_commands_file):
        """
        Loads a collection of commands from a json file. Follow `commands.schema` for the format of this json file
        :param path_to_commands_file: the path of the file, including the name and extension
        """
        with open(path_to_commands_file, 'r') as file:
            commands = json.load(file)
            for command in commands:
                self.add_command(**command)

    def add_step(self, command_name):
        """
        Adds a command to the built-in cycle. When the cycle is run the commands will be called in the order they are
        added in.
        :param command_name: The name of the command to be added
        """
        if command_name not in self.commands.keys():
            raise RuntimeError(str(command_name) + " is not a registered command")
        self.steps.append(command_name)
        self._json_objects['steps'].append({"command_name": command_name})

    def add_component(self, component_type, match_case=False, absolute_path=False, **kwargs):
        """
        Acts as a component factory for the controller.
        :param component_type: A string that is linked to the component class to be created. If the class was loaded
        with the modules.json file this can be the keywords defined in that file. Otherwise, it will have to be
        dynamically loaded using the functions found in ngclib.utils.
        :param match_case: A boolean that represents if the exact case should be matched when dynamically loading the
        component class (default False)
        :param absolute_path: A boolean that represents if the component class should be treated as an absolute path
        when dynamically loading the component class (default False)
        :param kwargs: All the keyword arguments that are needed to initialize the loaded component class. The function
        will try to crash nicely if keyword arguments are missing. This list of arguments will also be stored to allow
        for the component to be rebuilt, but if a given value is not serializable it will drop that from the keyword
        arguments.
        :return: The created component (Component is also automatically added to the controller)
        """
        Component_class = load_from_path(path=component_type, match_case=match_case, absolute_path=absolute_path)
        count = Component_class.__init__.__code__.co_argcount - 1
        named_args = Component_class.__init__.__code__.co_varnames[1:count]
        try:
            component = Component_class(**kwargs)
        except TypeError as E:
            print(E)
            raise RuntimeError(str(E) + "\nProvided keyword arguments:\t" + str(list(kwargs.keys())) +
                               "\nRequired keyword arguments:\t" + str(list(named_args)))

        check_attributes(component, ["name", "verify_connections"], fatal=True)
        self.components[component.name] = component

        obj = {"component_type": component_type, "match_case": match_case, "absolute_path": absolute_path} | kwargs
        bad_keys = check_serializable(obj)
        for key in bad_keys:
            del obj[key]
            print("Failed to serialize \"" + str(key) + "\" in " + component.name)

        self._json_objects['components'].append(obj)

        return component

    def add_command(self, command_type, command_name, match_case=False, absolute_path=False, component_names=None,
                    **kwargs):
        """
        Acts as a factory to create command.
        In addition to adding command objects to the controllers command list, commands are also set to their attributes
        on the controller. For example if a command named `step` is added myController.runCommand("step", ...) is equivalent
        to myController.step(...). There is
        :param command_type: A string that is linked to the command class to be created. If the class was loaded
        with the modules.json file this can be the keywords defined in that file. Otherwise, it will have to be
        dynamically loaded using the functions found in ngclib.utils.
        :param command_name: A string that is the name of the command, this is the keyword that will be called
        elsewhere to execute this command.
        :param match_case: A boolean that represents if the exact case should be matched when dynamically loading the
        command class (default False)
        :param absolute_path: A boolean that represents if the command class should be treated as an absolute path
        when dynamically loading the command class (default False)
        :param component_names: A list of component names to be passed to the command's constructor. Internally it will
        convert the strings to the actual component objects so they must exist in the controller prior to this function
        being called.
        :param kwargs: All the keyword arguments that are needed to initialize the loaded command class. The function
        will try to crash nicely if keyword arguments are missing. This list of arguments will also be stored to allow
        for the component to be rebuilt, but if a given value is not serializable it will drop that from the keyword
        arguments.
        :return: The created command (Command is also automatically added to the controller)
        """
        Command_class = load_from_path(path=command_type, match_case=match_case, absolute_path=absolute_path)
        if not callable(Command_class):
            raise RuntimeError("The object named \"" + Command_class.__name__ + "\" is not callable. Please make sure "
                                                                                "the object is callable and returns a "
                                                                                "callable object")
        if component_names is not None:
            componentObjs = [self.components[name] for name in component_names]
        else:
            componentObjs = []

        count = Command_class.__init__.__code__.co_argcount - 1
        named_args = Command_class.__init__.__code__.co_varnames[1:count]
        try:
            command = Command_class(components=componentObjs, controller=self, command_name=command_name, **kwargs)
        except TypeError as E:
            print(E)
            raise RuntimeError(str(E) + "\nProvided keyword arguments:\t" + str(list(kwargs.keys())) +
                               "\nRequired keyword arguments:\t" + str(list(named_args)))

        self.commands[command_name] = command
        self.__setattr__(command_name, command)

        obj = {"command_type": command_type, "command_name": command_name, "match_case": match_case,
               "absolute_path": absolute_path, "component_names": component_names} | kwargs
        bad_keys = check_serializable(obj)
        for key in bad_keys:
            del obj[key]
            print("Failed to serialize \"" + str(key) + "\" in " + command_name)

        self._json_objects['commands'].append(obj)
        return command

    def runCommand(self, command_name, *args, **kwargs):
        """
        Runs the given command
        :param command_name: The name of the command to run
        :param args: positional arguments to be passed into the command
        :param kwargs: keyword arguments to be passed into the command
        """
        command = self.commands.get(command_name, None)
        if command is None:
            raise RuntimeError("Can not find command: " + str(command_name))
        command(*args, **kwargs)

    def save_to_json(self, directory, model_name=None, custom_save=True):
        """
        Dumps all the required json files to rebuild the current controller to a specified directory. If there is a
        `save` command present on the controller and custom_save is True, it will run that command as well.
        :param directory: The top level directory to save the model to
        :param model_name: The name of the model, if None or if there is already a model with that name a uid will be
        used or appended to the name respectively. (default None)
        :param custom_save: A boolean that if true will attempt to call the `save` command if present on the controller
        (default True)
        :return: A tuple where the first value is the path to the model, and the second is the path to the custom save
        folder if custom_save is true and None if false
        """
        path = make_unique_path(directory, model_name)

        with open(path + "/commands.json", 'w') as fp:
            json.dump(self._json_objects['commands'], fp, indent=4)

        with open(path + "/steps.json", 'w') as fp:
            json.dump(self._json_objects['steps'], fp, indent=4)

        with open(path + "/components.json", 'w') as fp:
            json.dump(self._json_objects['components'], fp, indent=4)

        with open(path + "/connections.json", 'w') as fp:
            json.dump(self._json_objects['connections'], fp, indent=4)

        if custom_save:
            os.mkdir(path + "/custom")
            if check_attributes(self, ['save']):
                self.save(path + "/custom")
            else:
                warnings.warn("Controller doesn't have a save command registered. No custom saving happened")

        return (path, path + "/custom") if custom_save else (path, None)

    def load_from_dir(self, directory, custom_folder="/custom"):
        """
        Builds a controller from a directory. Designed to be used with save_to_json
        :param directory: The path to the model
        :param custom_folder: The name of the custom data folder for building components. (default `/custom`)
        """
        self.make_components(directory + "/components.json", directory + custom_folder)
        self.make_connections(directory + "/connections.json")
        self.make_commands(directory + "/commands.json")
        self.make_steps(directory + "/steps.json")