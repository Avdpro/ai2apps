## CokeCodes CLI tools
CLI tools are applications run in terminal with **Text User Interface**.

### UNIX Commands port
I had port some of UNIX terminal command into CokeCodes. They are coded in Javascript. Currently their behavior is not 100% same with UNIX.  
They are: **cat, cd, clear, cp, echo, ls, mkdir, mv, pwd, rm, sh, unzip, zip**

### CokeCodes tools
- **coke**: execute javascript/sh file in terminal.
- **cokemake**: the **make** tool for CokeCodes, this is just a initial version.
- **disk**: Manage disks, sync disks with cloud repository.
- **cloud**: CokeCodes accout CLI tool. **Currently it's the only way to logout your account**.
- **pkg**: Install/ manage packages.

### Dev. tools
- **babel** the **babel in web
- **rollup** a rough port of rollup, only works with config file (*rollup -c*).
- **terser** the web port of terser, work with rollup and cokemake.

### More reinforcements incomming.
Current tools are coded for making the CokeCodes, a lot of them are not fully functional as they should. They will be upgraded day by day. More tools will join the team, too.