@echo off
rem Update Focus Tools and then execute the code checker passing the first argument.
rem
"%ProgramFiles%\MEDITECH\MTAppDwn.exe" -silent -update "%ProgramFiles%\MEDITECH\M-AT Tools\Client.mtad"
"%ProgramFiles%\MEDITECH\M-AT Tools\M-AT_Code_Checker\at_code_checker.exe" %*
