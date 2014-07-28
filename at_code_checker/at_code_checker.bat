@echo off
rem Update Focus Tools and then execute the code checker passing the first argument.
rem
rem TODO: remove the 'Test' in "M-AT Tools Test" before releasing.
"%ProgramFiles%\MEDITECH\MTAppDwn.exe" -silent -update "C:\Program Files\MEDITECH\M-AT Tools Test\Client.mtad"
"%ProgramFiles%\MEDITECH\M-AT Tools Test\M-AT_Code_Checker\at_code_checker.exe" %1
