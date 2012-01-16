#!/bin/sh

mkdir /etc/service/libfitbit
mkdir /etc/service/libfitbit/log
cp svscan/run /etc/service/libfitbit/run
cp svscan/log-run /etc/service/libfitbit/log/run
chmod +x /etc/service/libfitbit/run /etc/service/libfitbit/log/run
