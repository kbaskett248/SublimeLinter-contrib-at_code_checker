@echo off
rem Update Focus Tools and then execute the code checker passing the first argument.
rem
"C:\Program Files\MEDITECH\MTAppDwn.exe" -silent -update "C:\Program Files\MEDITECH\M-AT Tools\Client.mtad"
"C:\Program Files\MEDITECH\M-AT Tools\M-AT_Code_Checker\at_code_checker.exe" %*
