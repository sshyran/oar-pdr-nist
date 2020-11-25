"""
package that provides implementations of commands that can part of a command-line interface and 
which are part of the publishing workflow.  See nistoar.pdr.cli and the pdr script for info on 
the general CLI infrastructure.

This module defines a set of subcommands to a command called (by default) "pub".  These subcommands
include
  - prepupd:  setup a metadata bag based on the last published version of a specified dataset.
"""
from . import prepupd
from ... import cli

default_name = "pub"
help = "manage a publishing workflow via subcommands"
description = \
"""apply an action that is part of the publishing workflow"""

def load_into(subparser, as_cmd=None):
    """
    load this command into a CLI by defining the command's arguments and options.
    :param argparser.ArgumentParser subparser:  the argument parser instance to define this command's 
                                                interface into it 
    """
    p = subparser
    p.description = description

    if not as_cmd:
        as_cmd = default_name
    out = cli.CommandSuite(as_cmd, p)
    out.load_subcommand(prepupd)
    return out

    
