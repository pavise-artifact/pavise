#!/bin/bash
rm -rf /pmem0p1/pmdk/*
if [[ $4 == "pgl" ]]
then
    path="/home/nvm-admin/pmdk-pangolin/src"
elif [[ $4 == "pmdk14" ]]
then
    path="/home/nvm-admin/pmdk-1.4/src"
elif [[ $4 == "pmdk15" ]]
then
    path="/home/nvm-admin/pmdk-1.5/src"
elif [[ $4 == "pmdk18" ]]
then
    path="/home/nvm-admin/pmdk-1.8-baseline/src"
elif [[ $4 == "pmdk110" ]]
then
    path="/home/nvm-admin/pmdk-1.10/src"
elif [[ $4 == "pgl110" ]]
then
    path="/home/nvm-admin/pgl-1.10/src"
else
    path="/home/nvm-admin/pavise/pmdk-1.10/src"
fi
   
LD_LIBRARY_PATH="$path/nondebug/:$LD_LIBRARY_PATH"
#export PMEMOBJ_LOG_LEVEL="4"
gdb --args $path/benchmarks/pmembench map_insert -n $1 -d 256 -t $2 -f /pmem0p1/pmdk/map -T $3
echo $LD_LIBRARY_PATH
echo $PMEMOBJ_LOG_LEVEL
rm -rf /pmem0p1/pmdk/*

