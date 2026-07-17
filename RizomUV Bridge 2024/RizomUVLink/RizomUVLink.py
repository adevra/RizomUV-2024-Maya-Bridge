# MIT License
# 
# Copyright (c) 2026 Rizom-Lab
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import os

# python 3.4+
from pathlib import Path

from RizomUVLinkBase import CRizomUVLinkBase
from RizomUVLinkBase import CZEx

class CRizomUVLink(CRizomUVLinkBase):
    def __init__(self):
        super().__init__()
        self.port = None

    def RunRizomUV(self, exePath : str = None, port : int = None, connect : bool = True, wait : bool = True) -> int:
        """ Runs RizomUV, connect to the instance and wait for it to be ready
        
            RizomUV standalone version must be 2025.0 or later. 
            
            If RizomUV is already running, another instance will be ran
            and the existing one will be left untouched and will be disconnected
            from this object instance.
         
            returns:
                The TCP port number used by the RizomUV instance to communicate.
         """
        if exePath is None:
            exePath = self.RizomUVPath()
        if exePath is None:
            raise CZEx("RizomUV executable path not found. Re-installing RizomUV should fix this issue.")

        # define the TCP port used for communication
        if port == None:
            # search a free TCP port on the dynamic range
            for p in range(49152, 65534):
                if not self.TCPPortIsOpen(p):
                    self.port = p
                    break
                if p == 65533:
                    raise CZEx("No available TCP Port found. This shouldn't be the case. Might worth to check your firewall settings just in case.")
        else:
            if self.TCPPortIsOpen(port):
                raise CZEx("Port " + str(port) + " is already in use, please connect using another port")
            self.port = port
        
        # change current directory to the RizomUV executable directory
        os.chdir(os.path.dirname(exePath))

        # run RizomUV asynchronously
        import subprocess
        subprocess.Popen(exePath + " -id " + str(self.port))

        # connect the the instance
        if connect:
            self.Connect(self.port)
        
        ## wait for RizomUV initialisation to complete
        if wait:
            # calling this will force to wait for RizomUV to be ready
            version = self.RizomUVVersion()

        return self.port
        
    def RizomUVPath(self) -> str:
        import platform
        if platform.system() == "Windows":
            return self.RizomUVWinPath()
        elif platform.system() == "Darwin":
            return "/Applications/RizomUV.app/Contents/MacOS/RizomUV" #TODO
        elif platform.system() == "Linux":
            return "/usr/bin/RizomUV" #TODO
        else:
            raise CZEx("Unsupported platform: " + platform.system())
    
    def RizomUVWinPath(self):
        return str(Path(__file__).resolve().parent.parent) + "/rizomuv.exe"
        
    def RizomUVWinRegisterInstallPath(self):
        """ Returns the path to the most recent version 
            of the RizomUV installation directory on the system using
            the windows registry.
            
            Try versions from 2029.10 to 2025.0 included
        """
        import winreg

        for i in range(9, 5, -1):
            for j in range(10, -1, -1):
                if i == 2 and j < 2:
                    continue
                path = "SOFTWARE\\Rizom Lab\\RizomUV VS RS 202" + str(i) + "." + str(j)
                try:
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path)
                    exePath = winreg.QueryValue(key, "rizomuv.exe")
                    return os.path.dirname(exePath)
                except FileNotFoundError:
                    pass

        return None
    