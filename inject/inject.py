import random
import sys
import os
import subprocess
import time
from typing import List
SHADOW_BASE = 0x30000000000
CSIZE = 512
CUTOFF = 0x444000
NUM_ERR_BIT_FLIPS = 1
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


def inject_one(byte_offset, fd):
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

def inject_n_bytes(byte_offset, fd, n):
    fd.seek(byte_offset)
    tmp = fd.read(n) # read n bytes
    tmpa = bytearray(tmp)
    for index in range(len(tmpa)):
        # invert all bits in the n bytes
        tmpa[index] ^= 0xFF
        # inject 0
        #tmpa[index] = 0x00
    fd.seek(byte_offset)
    fd.write(tmpa)

if len(sys.argv) != 4:
    print("Usage: python3 inject.py num_err_bits_to_flip 1/err_rate benchmark")
    exit()

#count = int(sys.argv[1])
NUM_ERR_BIT_FLIPS = int(sys.argv[1])
error_rate = int(sys.argv[2])
workload = sys.argv[3]

print("Flipping", NUM_ERR_BIT_FLIPS,"bit(s) at a time.")
print("Error rate ^ -1 = ", error_rate)
print("Workload =", workload)
print("NUM_ITERS =", NUM_ITERS)

# fix seed for now
#random.seed(1)
random.seed()

path = '/pmem0p1/nvm-admin/pmdk/map'


def inject_workload(workload,err_rate,num_err_bits_to_flip):
    if (num_err_bits_to_flip != 1 and num_err_bits_to_flip % 8 != 0):
        raise ValueError('Number of error bits to inject is not 1 and not a multiple of 8.')

    logfile = open(workload)
    lines = logfile.readlines()
    chunks = []
    size = 512
    
    for line in lines:
        if(line.find("computing") != -1):
            begin = line.find("0x")
            end = line.find(",")
            addr = int(line[begin:end],base=16)
            chunks.append([addr,addr+size])
    
    merged = merge(chunks)

    if (num_err_bits_to_flip == 1):
        P = err_rate/8 #this compensates for the fact that each byte will have at most 1 bit error
    else :
        P = err_rate # dont need this compensation for n byte errors
        print("error rate not divide by 8", P)

    failcount = 0
    crashcount = 0
    detectfailcount = 0
    recoverfailcount = 0
    
    for j in range(NUM_ITERS):
        icount = 0
        injectlist = []
        r = subprocess.run(["/home/nvm-admin/pavise/runinject.sh", "10","1","hashmap_tx","1"],stdout=subprocess.DEVNULL)
        time.sleep(1) # the sleep is needed here or else pmdk benchmark crashes sometimes
        #os.fsync(pmfile)
        #r.stdout
        fsize = os.path.getsize(path)
        pmfile = open(path,'rb+')
        # Trim file size to working set
        fsize = CUTOFF if fsize > CUTOFF else fsize
    
        if (num_err_bits_to_flip == 1):
            for interval in merged:
                #chunk_offset = random.randrange(size)
                begin = interval[0]
                end = interval[1]
                # for each address (byte) in the chunk, inject 1 bit flip
                for i in range(begin,end):
                    randn = random.randrange(P)
                    if(randn == 0):
                        inject_one(i - SHADOW_BASE,pmfile)
                        injectlist.append((i) & ~(size-1))
                        #print("inject list append ", (i) & ~(size-1))
                        icount += 1
        else: # num_err_bits_to_flip is a multiple of 8
            num_err_bytes_to_flip = int(num_err_bits_to_flip/8)
            for interval in merged:
                begin = interval[0]
                end = interval[1]
                # loop through each num_err_bytes_to_flip bytes in the interval
                for i in range(begin,end,num_err_bytes_to_flip):
                    randn = random.randrange(P)
                    if(randn == 0): # flip 
                        inject_n_bytes(i - SHADOW_BASE,pmfile,num_err_bytes_to_flip)
                        injectlist.append((i) & ~(size-1))
                        icount += 1
        pmfile.close()
        cmd = subprocess.Popen(["/home/nvm-admin/pavise/runinject.sh", "10","1","hashmap_tx","0"],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            cmd_out, cmd_err = cmd.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            cmd.kill() # make sure the process doesnt just hang there forever
            crashcount += 1
            failcount += 1
            print(icount, "injected, crashed, timeout")
            print("+++++++++++++++++++++++++++++++++++++++++++ iteration",j)
            continue
        if cmd.returncode:
            crashcount += 1
            failcount += 1
            print(icount, "injected, crashed")
            print("+++++++++++++++++++++++++++++++++++++++++++ iteration",j)
            continue
    
        output = cmd_out.decode('utf-8')
        sindex = output.find("#s=")
        findex = output.find("#f=")
        eindex = output.find("#end")
        rsuccess = int(output[sindex+3:findex])
        rfail = int(output[findex+3:eindex])
        injectset = set(injectlist)
        ##print("inject list", injectlist)
   
        print(len(injectset), "injected," ,rsuccess+rfail,"detected,", rsuccess, "success,", rfail, "fail")
        print("+++++++++++++++++++++++++++++++++++++++++++ iteration",j)
        sys.stdout.flush()
        if rfail != 0:
            recoverfailcount += 1
            failcount += 1
            continue
        if len(injectset) - (rsuccess + rfail) > 1:
            detectfailcount += 1
            failcount += 1


    print(crashcount,"crashed.",detectfailcount,"detect failed.",recoverfailcount,"recovery failed. Total",workload,failcount)
    sys.stdout.flush()
#end inject_workload

print("=========================================================================== err rate =",error_rate)
print("=============================================================== workload =",workload)
inject_workload(workload,error_rate,NUM_ERR_BIT_FLIPS)

quit()
