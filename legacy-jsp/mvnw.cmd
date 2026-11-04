@echo off
if exist "%~dp0maven-local\apache-maven-3.9.9\bin\mvn.cmd" (
    "%~dp0maven-local\apache-maven-3.9.9\bin\mvn.cmd" %*
) else (
    mvn %*
)
