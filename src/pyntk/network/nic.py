##
# This file is part of Netsukuku
# (c) Copyright 2007 Alberto Santini <alberto@unix-monk.com>
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

import commands
import logging
import re

class Nic:
  """ this class is used to manage network interfaces """
  def __init__(self, net_device):
    """ net_device: nic's name """
    
    self.net_device = net_device

  def _exec_ipl(self, ipl_str):
    """ ipl_str: ip link string (or ip address) """
      
    # execute ip link
    status, output = commands.getstatusoutput(ipl_str)
                
    # check if everything went good.. if not, log!
    if(status != 0):
      logger.error(output)
      
    return output

  def nic_up(self):
    """ bring up the interface """
    _ip_link_nic_updown("up")
  
  def nic_down(self):
    """ bring down the interface """
    _ip_link_nic_updown("down")
    
  def nic_change_address(self, address):
    """ change the interface's address """
    _ip_link_nic_change_address(address)
    
  def nic_retrieve_info(self, ip_version):
    """ return the following tuple:
        (up_or_down, address)
        up_or_down: True (nic is up) | False (nick is down)
        address: nic's address
    """
    return _ip_address_show(ip_version)
    
  def _ip_address_show(self, ip_version):
    """ return infos about the interface, obtained via ip address """
    
    # generate ip address string
    ipa_str = "ip address show dev " + str(self.det_device)
    
    # execute ip address
    ipa_out = _exec_ipl(ipa_str)
    
    # check wether the interface is up or down
    up_reg = re.compile("up", re.IGNORECASE)
    up_mat = up_reg.search(ipa_out)
    if up_mat is None:
      up_or_down = False
    else:
      up_or_down = True
    
    # check wether we're using IPv6 or not
    v6_reg = re.compile("inet6")
    v6_mat = v6_reg.search(ipa_out)
    if v6_mat is None:
      if ip_version == 6:
        logger.error("No IPv6 address associated with " + str(self.net_device))
        return (None, None)

    # find the ip address
    if ip_version == 6:
      ip_reg = re.compile("inet6 (.*:){5}(.*)\/")
      ip_mat = ip_reg.search(ipa_out)
      if ip_mat is None:
        logger.error("No valid IPv6 address found for " + str(self.net_device))
        return (None, None)
      else:
        raw_address = ip_mat.group()
        # remove "inet6 " and "/"
        address = raw_address[6:-1]
    else:
      ip_reg = re.compile("inet (.*\.){3}(.*)\/")
      ip_mat = ip_reg.search(ipa_out)
      if ip_mat is None:
        logger.error("No valid IPv4 address found for " + str(self.net_device))
        return (None, None)
      else:
        raw_address = ip_mat.group()
        # remove "inet " and "/"
        address = raw_address[5:-1]
    
    return (up_or_down, address)

  def _ip_link_nic_up(self, up_or_down):
    """ bring up/down the interface via ip link """
    
    # generate ip link string
    ipl_str = "ip link set dev " + str(self.net_device) + " " + str(up_or_down)
    
    # execute ip link
    _exec_ipl(ipl_str)

  def _ip_link_change_address(self, address):
    """ change the interface's address via ip link """
    
    # generate ip link string
    ipl_str = "ip link set dev " + str(self.net_device) + " address " + str(address)
    
    # execute ip link
    _exec_ipl(ipl_str)