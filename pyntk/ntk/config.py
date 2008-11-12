##
# This file is part of Netsukuku
# (c) Copyright 2007 Daniele Tricoli aka Eriol <eriol@mornie.org>
#
# This source code is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as published
# by the Free Software Foundation; either version 2 of the License,
# or (at your option) any later version.
#
# This source code is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# Please refer to the GNU Public License for more details.
#
# You should have received a copy of the GNU Public License along with
# this source code; if not, write to:
# Free Software Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
##

import imp
import os
import sys

if sys.platform == 'linux2':
    global_settings = dict(
        CONFIGURATION_DIR = '/etc/netsukuku',
        CONFIGURATION_FILE = 'settings.py',
        DATA_DIR = '/usr/share/netsukuku',
        PID_DIR  = '/var/run',
    )
else:
    raise Exception('Your platform is not supported yet.')

class Settings(object):

    def __init__(self):
        for setting in global_settings:
            # Configuration settings must be uppercase
            if setting == setting.upper():
                setattr(self, setting, global_settings[setting])

        self._load_configuration_file()

    def _load_configuration_file(self):
        configuration_file = os.path.join(self.CONFIGURATION_DIR,
                                          self.CONFIGURATION_FILE)
        try:
            user_settings = imp.load_source('configuration_file',
                                            configuration_file)
        except IOError, e:
            raise IOError("Could not load '%s': %s" % (configuration_file, e))

        except SyntaxError, e:
            raise SyntaxError("Error in '%s': %s" % (configuration_file, e))

        for setting in dir(user_settings):
            if setting == setting.upper():
                setting_value = getattr(user_settings, setting)
                setattr(self, setting, setting_value)

settings = Settings()