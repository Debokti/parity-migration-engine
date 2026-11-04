@echo off
cd /d "%~dp0"
java -cp "target/classes;target/lib/*" com.scf.config.ServerMain
