#!/bin/bash

THREADS=16

dir_name="pgl_full_sweep2"
csv_name=$dir_name

mkdir -p $dir_name
echo "pgl" > ${dir_name}/${csv_name}.csv
echo numrows,errorsize,errrate,bench,rep_fail_cnt,parity_fail_cnt,total_fail_cnt, \
     total_iters,recover_success_rate >> ${dir_name}/${csv_name}.csv

parallel --bar --gnu -j$THREADS  --header : \
    '
    # how do I use the existing var
    dir_name="pgl_full_sweep2"
    csv_name=$dir_name

    echo Running error_size={error_size} error_rate={error_rate} benchmark={benchmark} parity_num_rows={parity_num_rows}
    python3 injectpgl.py {error_size} {error_rate} {benchmark} {parity_num_rows} \
        > ${dir_name}/numrows{parity_num_rows}_errsize{error_size}_errrate{error_rate}_{benchmark}_log

    # extract results from log
    # rev | cut | rev selects cut element in reverse order
    rep_fail_cnt=`cat ${dir_name}/numrows{parity_num_rows}_errsize{error_size}_errrate{error_rate}_{benchmark}_log \
        | tail -n 1 | rev | cut -d" " -f5 | rev`
    parity_fail_cnt=`cat ${dir_name}/numrows{parity_num_rows}_errsize{error_size}_errrate{error_rate}_{benchmark}_log \
        | tail -n 1 | rev | cut -d" " -f4 | rev`
    total_fail_cnt=`cat ${dir_name}/numrows{parity_num_rows}_errsize{error_size}_errrate{error_rate}_{benchmark}_log \
        | tail -n 1 | rev | cut -d" " -f3 | rev`
    total_iters=`cat ${dir_name}/numrows{parity_num_rows}_errsize{error_size}_errrate{error_rate}_{benchmark}_log \
        | tail -n 1 | rev | cut -d" " -f2 | rev`
    recover_success_rate=`cat ${dir_name}/numrows{parity_num_rows}_errsize{error_size}_errrate{error_rate}_{benchmark}_log \
        | tail -n 1 | rev | cut -d" " -f1 | rev`

    echo ${rep_fail_cnt} ${parity_fail_cnt} ${total_fail_cnt} ${total_iters} ${recover_success_rate}
    sem --id mystr echo {parity_num_rows},{error_size},{error_rate},{benchmark}, \
        $rep_fail_cnt,$parity_fail_cnt,$total_fail_cnt,$total_iters,$recover_success_rate >> ${dir_name}/${csv_name}.csv | cat
    ' \
    ::: error_size 1 8 16 32 64 \
    ::: error_rate 10000 100000 1000000 10000000 \
    ::: benchmark pgltx pglctree pglbtree pglrbtree pglrtree \
    ::: parity_num_rows 20 40 60 80 100 10000

#::: error_size 1 8 16 32 64 \
#::: error_rate 10000 100000 1000000 10000000 \
#::: benchmark pgltx pglctree pglbtree pglrbtree pglrtree \
#::: parity_num_rows 20 40 60 80 100
