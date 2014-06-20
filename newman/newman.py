"""
Builds out an arugment parser based on function signatures in various modules.
Each module is mapped to a sub-command name space, and each function of that
module is mapped to an operation of that sub command.  Parameters to that
function are made into command line arguments.  Invocation looks like:


command sub-command operation REQUIRED_ARG [...] [--OPTIONAL-ARG VAL]
"""
import argparse
import inspect
import logging
import sys


def _coerce_bool(some_str):
    """Stupid little method to try to assist casting command line args to
    booleans
    """
    if some_str.lower().strip() in ['n', 'no', 'off', 'f', 'false', '0']:
        return False
    return bool(some_str)


class Newman(object):
    '''Container class to hold a bunch of customized (sub)parsers
    '''
    # TODO: Move this to some kind of optional plugin? Don't want to require
    # Raven for folks who aren't using sentry.
    def register_sentry_handler(self, sentry_dns, log_level=logging.ERROR):
        from raven.handlers.logging import SentryHandler
        sentry_handler = SentryHandler(sentry_dns)
        sentry_handler.setLevel(log_level)
        self.logger.addHandler(sentry_handler)

    def __init__(self, description="A parser nobody bothered to customize",
                 sentry_dns=None, top_level_args=None):
        """Build an argument parser from module definitions and run the
        function we were asked for

        `top_level_args` should be a dictionary of argument name: default value
        that will be handled by the function that instantiates Newman instead
        of the operation that is ultimately called.
        Use case: global config options/paths
        """
        self.logger = logging.getLogger()
        self.parser = argparse.ArgumentParser(
            description=description,
            add_help=True,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )

        self.sub_parsers = self.parser.add_subparsers(
            title='task modules',
            description='The following modules were loaded as task namespaces',
            dest='module'
        )
        if sentry_dns:
            self.register_sentry_handler(sentry_dns)

        self.default_top_level_args = top_level_args or {}
        for targ, default in top_level_args.items():
            arg_type = type(default)
            if isinstance(default, bool):
                arg_type = _coerce_bool
            self.parser.add_argument('--' + targ.replace('_', '-'),
                                     type=arg_type, default=default)

        self._parsed_args = None

    @property
    def func(self):
        if not self._parsed_args:
            self.parse_args()
        return self._parsed_args['func']

    @property
    def real_args(self):
        if not self._parsed_args:
            self.parse_args()
        return self._parsed_args['real_args']

    @property
    def top_level_args(self):
        if not self._parsed_args:
            self.parse_args()
        return self._parsed_args['top_level_args']

    def parse_args(self):
        """Generates a dictionary of parsed arguments.

        `func` is the operation to be run.
        `top_level_args` is a dict of any arguments that are used in the
        calling proces.
        `real_args` are the arguments that the operation will be invokes with.
        """
        args = self.parser.parse_args()  # oh the possibilities...
        func = args.func  # this gets plumbed through by load_module
        real_args = []  # actual positional args we'll be sending to func
        top_level_args = {}  # args to be used by caller process, not operation

        # yay, even more weird signature hacking. Try to turn the argparse
        # arguments we got (if any) back into regular function arguments
        fargs, varargs, null, fdefaults = inspect.getargspec(func)

        for targ in self.default_top_level_args:
            if hasattr(args, targ):
                top_level_args[targ] = getattr(args, targ)
        for farg in fargs:
            if hasattr(args, farg):
                # this function cares about this passed in arg
                real_args.append(getattr(args, farg))
        if varargs:
            # this func takes varags
            real_args += getattr(args, varargs)

        self._parsed_args = {
            'func': func,
            'top_level_args': top_level_args,
            'real_args': real_args
        }

    def go(self):
        """Call this in your CLI entry point once you've loaded all your tasks
        (via load_module()). It will parse any command line args, choose the
        correct function to call, and call it with your arguments, then exit.
        If the arguments specify an unknown command, the usage help will be
        printed and the program will exit with code 1
        """
        real_args = self.real_args
        func = self.func

        exit_code = 2
        if func:
            try:
                exit_code = func(*real_args)
            except Exception as e:
                self.logger.exception("%s (in loaded task)", e)
                raise
        sys.exit(exit_code)

    def load_module(self, module, sub_command):
        """Load tasks from the given module, and makes them available under the
        given subcommand.
        Build the argument parser for the collected tasks.  The sub-parsers get
        attached to the passed in top level parser under the previously
        registered sub-commands.


        :param str module_name: python style module name - foo.bar.baz
        :param str sub_command: the command name to associate with this module
        :param top_level: The configured top level command parser
        :type top_level: argparse.ArgumentParser
        """
        # Add a sub-parser for this sub-command
        mod_parser = self.sub_parsers.add_parser(
            sub_command,
            description=module.__doc__,
            help=module.__doc__
        )
        mod_sub_parsers = mod_parser.add_subparsers(
            title='tasks under %s' % sub_command,
            help='The following are valid task commands',
            dest='cmd'
        )

        for func_name, func_obj in inspect.getmembers(module,
                                                      inspect.isfunction):
            # skip if we are looking at a private function
            if func_name.startswith('_'):
                continue
            # TODO: Not sure what to do about this
            if (not inspect.getmodule(func_obj).__name__.endswith(
                    module.__name__)):
                # this check tries to avoid functions at the module level that
                # were imported and not defined in that module
                continue
            # give each function it's own sub parser under its parent module
            # and try to provide options based on the function signature
            func_parser = mod_sub_parsers.add_parser(
                func_name,
                help=func_obj.__doc__,
                formatter_class=argparse.ArgumentDefaultsHelpFormatter
            )
            func_parser.set_defaults(func=func_obj)

            # get the signature of the method we're setting up
            args, varargs, _, defaults = inspect.getargspec(func_obj)
            if varargs:
                # used if a function accepts *args
                func_parser.add_argument(varargs, nargs='*')

            if defaults:
                # defaults arrives as a tuple of argument defaults, but it's
                # indexed from the furthest right argument. So it's possible
                # you may get ['arg1', 'arg2'] as the args and (10,) as the
                # defaults, where 10 is the default value for arg2. Confusing
                # and weird, yes.
                defaults = list(defaults)
                defaults.reverse()

            # now for each argument we found, go backwards (see above for why)
            positionals = []
            for cnt, arg in enumerate(reversed(args)):
                if defaults and cnt < len(defaults):
                    # we're basically going backwards, but the arg parser
                    # doesn't care so this works. The signature made this
                    # optional, so try to make an educated guess as to the type
                    # of variable
                    kwargs = {
                        'help': 'taken from signature',
                        'default': defaults[cnt],
                    }
                    if isinstance(defaults[cnt], bool):
                        kwargs['type'] = _coerce_bool
                    elif defaults[cnt] is None:
                        pass
                    else:
                        kwargs['type'] = type(defaults[cnt])
                    func_parser.add_argument("--%s" % arg.replace("_", "-"),
                                             **kwargs)
                else:
                    # this is a positional arg, that we know pretty much
                    # nothing about
                    positionals.append(arg)
                # Finally reverse the positional args again, so they're in the
                # right order
                for arg in reversed(positionals):
                    func_parser.add_argument(arg, help='taken from signature')
