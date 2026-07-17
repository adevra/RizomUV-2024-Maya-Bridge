# RizomUVLink

An open source Python module to control a RizomUV Standalone instance from a DCC

## Description

RizomUVLink is a Python module made to control a RizomUV Standalone instance from any Python capable DCC or from any Python program.

It consists from a set of compiled Python modules, some third party compiled libraries and some Python code. The libraries are present in several version, one for each version of Python and for each OS.

It has the following features:
* Permits the control of a RizomUV instance thru its API's features directly from Python code running on the DCC
* Allows creation of "live link type bridges" using fast memory transfers from DCC to RizomUV and vice & versa
* Provides method helpers to facilitate most used tasks, i.e: launch the most recent RizomUV version on the OS
* Detect connection losts (RizomUV crash for instance) to prevent infinite loops on the DCC's plugin

The main principle is that commands and data can be emitted using the RizomUVLink module and they will be transfered (by IPC) to a specified RizomUV Standalone running instance. Data present in the RizomUV instance can also be retreived from RizomUVLink.

## Getting Started

### Dependencies

* RizomUV Standalone version 2026.0 or superior, available at https://rizom-lab.com
* Python 3.6.X | 3.7.X | 3.8.X | 3.9.X | 3.10.X | 3.11.X | 3.12.X | 3.13.X (tell us if you need other versions of Python)

### Installing

The RizomUVLink folder is located in the RizomUV's installation directory. Installing RizomUV itself using its setup is enough.

On Windows platform the location of the last RizomUV installation directory can be retreived from this Python code:

    def RizomUVWinRegisterInstallPath():
        """ Returns the path to the most recent version 
            of the RizomUV installation directory on the system using
            the windows registry.
            
            Try versions from 2029.10 to 2022.2 included
        """
        import winreg
        from pathlib import Path

        for i in range(9, 1, -1):
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

## Help

Please have a look at the **examples** folder, especially at the **Simple.py** file.

## Authors

Remi Arquier from Rizom-Lab. 

remi.arquier at rizom-lab.com

https://www.rizom-lab.com

## License

This project is licensed under the **MIT License** - see the LICENSE.md file for details

MIT License is a short and simple permissive license with conditions only requiring preservation of copyright and license notices. Licensed works, modifications, and larger works may be distributed under different terms and without source code. It allows a commercial use.

## Acknowledgments

* [ZeroMQ](https://https://zeromq.org/)
