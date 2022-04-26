#!/bin/bash
# 1: num inserts, 2: num threads, 3: workload, 4: delete file? 5: pgl or pavise
if [ $4 = "1" ]
then
    rm -rf /pmem0p1/pmdk/*
fi
if [[ $5 == "pgl" ]]
then
    path="/home/nvm-admin/pmdk-pangolin/src"
    LD_LIBRARY_PATH="$path/debug/:$LD_LIBRARY_PATH"
else
    path="/home/nvm-admin/pavise/pmdk-1.10/src"
    LD_LIBRARY_PATH="$path/nondebug/:$LD_LIBRARY_PATH"
fi
PMEMOBJ_LOG_LEVEL=0
#echo $PMEMOBJ_LOG_LEVEL
$path/benchmarks/pmembench map_insert -n $1 -d 256 -t $2 -f /pmem0p1/pmdk/map -T $3


