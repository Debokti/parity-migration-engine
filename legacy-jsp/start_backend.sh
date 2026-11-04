#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"
java -cp "target/classes:target/lib/*" com.scf.config.ServerMain
