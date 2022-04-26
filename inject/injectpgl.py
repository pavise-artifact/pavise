import random
import sys
import os
import subprocess
import math
from typing import List
SHADOW_BASE = 0x30000000000
PMEM_BASE = 0x10000000000
CSIZE = 512
CUTOFF = 0x444000
NUM_ITERS = 100


def merge(intervals: List[List[int]]) -> List[List[int]]:
    intervals.sort(key=lambda x: x[0])
    merged = []
    for interval in intervals:
        # if the list of merged intervals is empty or if the current
        # interval does not overlap with the previous, simply append it.
        if not merged or merged[-1][1] < interval[0]:
            merged.append(interval)
        else:
            # otherwise, there is overlap, so we merge the current and previous intervals
            merged[-1][1] = max(merged[-1][1], interval[1])
    return merged


def inject_one(byte_offset,fd):
    fd.seek(byte_offset)
    #byte = bytes(b'\xf0')
    #fd.write(byte)
    #return
    bit_offset = random.randrange(8)
    fd.seek(byte_offset)
    tmp = fd.read(1)
    tmpa = bytearray(tmp)
    mask = 1 << bit_offset
    flip_val = ~(tmpa[0] & mask)
    tmpa[0] = tmpa[0] | mask
    tmpa[0] = tmpa[0] & flip_val
    fd.seek(byte_offset)
    fd.write(tmpa)

#random.seed(1)
random.seed()


def inject_workload(workload,err_rate,num_err_bits_to_flip):
    if (num_err_bits_to_flip != 1 and num_err_bits_to_flip % 8 != 0):
        raise ValueError('Number of error bits to inject is not 1 and not a multiple of 8.')

    logfile = open(workload)
    lines = logfile.readlines()
    chunks = []
    repfilename = workload + 'rep'
    
    # sample line: PM WRITE at addr: 0x0000010000001a48, size = 8
    for line in lines:
        if(line.find("PM WRITE") != -1):
            begin = line.find("0x")
            end = line.find(",")
            addr = int(line[begin:end],base=16) # this is 0x0000010000001a48 in decimals
            begin = line.find("size")
            size = int(line[begin+7:]) # 8
            chunks.append([addr,addr+size]) # [0x0000010000001a48, 0x0000010000001a50]
    
    # looks like chunks contains chunks that were modified
    merged = merge(chunks)
    
    repfile = open(repfilename)
    replines = repfile.readlines()
    repchunks = dict()
    
    # I am guessing these are the metadatas which are replicated
    # sample line: <libpmemobj>: <0> [obj.c:961 obj_descr_create] src = 0x10000001000, rep = 0x10000304000, size = 2048
    for line in replines:
        if(line.find("src = ") != -1):
            begin = line.find("0x")
            end = line.find(",")
            src = int(line[begin:end],base=16) # 0x10000001000 in dec
            begin = line.find("rep = ")
            end = line.find(", size")
            rep = int(line[begin+6:end],base=16) # 0x10000304000 in dec
            begin = line.find("size = ")
            size = int(line[begin+7:]) # 2048. seems like both the src and the replica are of size 2048
            repchunks[src]= [src,rep,size]  #  [ 0x10000001000, 0x10000304000, 2048 ] using src as index as well
    
    for interval in merged:
        #chunk_offset = random.randrange(size)
        begin = interval[0]
        end = interval[1]
        #print(hex(begin),hex(end),end-begin)
    
    #print(len(merged),len(chunks))
    if (num_err_bits_to_flip == 1):
        P = err_rate/8 #this compensates for the fact that each byte will have at most 1 bit error
        #print(P)
    else :
        P = err_rate # dont need this compensation for n byte errors
        #print("error rate not divide by 8", P) 

    rep_failcount = 0
    parity_failcount = 0
    total_failcount = 0
    
    for j in range(NUM_ITERS):
        injectlist = []
        # Randomly create errors from the list of chunks that the program is writing to
        if (num_err_bits_to_flip == 1):
            for interval in merged: # for each "chunk" (pgl has varying chunk sizes)
                begin = interval[0]
                end = interval[1]
                for i in range(begin,end):
                    randn = random.randrange(P)
                    if(randn == 0):
                        injectlist.append(i)
        else: #num_err_bits_to_flip is a multiple of 8
            num_err_bytes_to_flip = int(num_err_bits_to_flip/8)
            for interval in merged:
                begin = interval[0]
                end = interval[1]
                for i in range(begin,end,num_err_bytes_to_flip):
                    randn = random.randrange(P)
                    if(randn == 0):
                        for k in range(i,i+num_err_bytes_to_flip):
                            # we need to add all num_err_bytes_to_flip bytes to the error list
                            injectlist.append(k)
                            #print("injecting error on ",hex(k))

        # Netadata replication unrecoverable error check
        for src in repchunks:
            src_err_count = 0
            rep_err_count = 0
            dst = repchunks[src][1]
            size = repchunks[src][2]
            for err in injectlist: # for each error we inject, check if the error is recoverable
                if err >= src and err < src + size:
                    # error within src object
                    src_err_count += 1
                if err >= dst and err < dst + size:
                    rep_err_count += 1
            # if both source and replica are injected with error, then fail
            if src_err_count > 0 and rep_err_count > 0:
                rep_failcount += 1
                print("Metadata replication unrecoverable error failed")
                break
   
        error_col_dict = {} # store which columns have errors. Ex. if an error is in address 0x1000 bit 3, then error_col_dict[0x1000][3]=1
        error_col_dict_byte_cols = {}

        zone_start_addr = 0x10000606000;
        zone_end_addr = 0x10000dc6000;
        rectangle_size = zone_end_addr - zone_start_addr; #8126464
        num_cols_bytes = math.ceil(rectangle_size/num_parity_rows) # number of columns if each column is 1 byte wide
        # parity unrecoverable error (two error bits in the same column) check
        if (num_err_bits_to_flip == 1):
            num_cols_bits = num_cols_bytes * 8 # number of columns if each column is 1 bit wide
            for err in injectlist: 
                if (err > zone_end_addr or err < zone_start_addr ):
                    # if the error is outside of the chunks range, skip
                    continue
                addr_offset = err - zone_start_addr
                err_col_number_bytes = addr_offset % num_cols_bytes # calculate which column the error belongs to
                bit_offset = random.randrange(8) # decide which bit to flip
                if (err_col_number_bytes in error_col_dict): # first check if the dict entry exists
                    if (bit_offset in error_col_dict[err_col_number_bytes]):
                        # an error already in this column. unrecoverable error
                        parity_failcount += 1
                        print("Parity unrecoverable error failed")
                        break
                    else: # register the new bit error
                        error_col_dict[err_col_number_bytes][bit_offset] = 1
                else:
                    # register the new bit error
                    if (err_col_number_bytes not in error_col_dict): # create key first if key does not exist
                        error_col_dict[err_col_number_bytes] = {}
                    error_col_dict[err_col_number_bytes][bit_offset] = 1
        else: # num_err_bits_to_flip is a multiple of 8
            # since errors are injected in bytes at a time and all errors are byte aligned, we only need to
            # keep track of parity columns in unit of bytes instead of bits. 
            # Ex. if an error is injected in address 0x1000, then error_col_dict_byte_level[0x1000] = 1
            for err in injectlist: 
                if (err > zone_end_addr or err < zone_start_addr ):
                    # if the error is outside of the chunks range, skip
                    continue
                addr_offset = err - zone_start_addr
                err_col_number_bytes = addr_offset % num_cols_bytes # calculate which column the error belongs to
                if (err_col_number_bytes in error_col_dict_byte_cols):
                    # an error already in this byte column. unrecoverable error
                    parity_failcount += 1
                    print("Parity unrecoverable error failed")
                    break
                else: # register the new bit error
                    error_col_dict_byte_cols[err_col_number_bytes] = 1
        print("+++++++++++++++++++++++++++++++++++++++++++ iteration",j)
        sys.stdout.flush()
    total_failcount = rep_failcount + parity_failcount
    recovery_success_rate = 1 - total_failcount / NUM_ITERS
    print("replication failcount, parity failcount, total failcout, iterations, recovery success rate: ", rep_failcount, parity_failcount, total_failcount, NUM_ITERS, recovery_success_rate)


if len(sys.argv) != 5:
    print("Usage: python3 injectpgl.py num_err_bits_to_flip 1/err_rate benchmark num_parity_rows")
    exit()

num_err_bit_flips = int(sys.argv[1])
error_rate = int(sys.argv[2])
workload = sys.argv[3]
num_parity_rows = int(sys.argv[4])


print("Flipping", num_err_bit_flips,"bit(s) at a time.")
print("Error rate ^ -1 = ", error_rate)
print("Workload =", workload)
print("NUM_ITERS =", NUM_ITERS)
print("num_parity_rows =", num_parity_rows)

#end inject_workload
# workloads: ['pglatm','pgltx','pglctree','pglbtree','pglrbtree','pglrtree']
print("=========================================================================== err rate =",error_rate)
print("=============================================================== workload =",workload)
inject_workload(workload,error_rate,num_err_bit_flips)

quit()
