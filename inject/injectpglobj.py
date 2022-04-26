import random
import sys
import os
import subprocess
from typing import List
SHADOW_BASE = 0x30000000000
PMEM_BASE = 0x10000000000
CSIZE = 512
CUTOFF = 0x444000


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

if len(sys.argv) != 2:
    print("input bit flip count as argument")
    exit()

count = int(sys.argv[1])

random.seed()

path = '/pmem0p1/pmdk/map'

logfile = open('pgltxobj')
lines = logfile.readlines()
chunks = []

for line in lines:
    if(line.find("pobj =") != -1):
        begin = line.find("pobj = ")
        end = line.find(", size")
        addr = int(line[begin+7:end],base=16)
        begin = line.find("size = ")
        size = int(line[begin+7:])
        chunks.append([addr,addr+size])

merged = merge(chunks)


P = 10000/8
failcount = 0

pmfile = open(path,'rb+')
inject_one(0x7441d0,pmfile)
pmfile.close()

for j in range(20):
    break
    icount = 0
    injectlist = []
    r = subprocess.run(["/home/nvm-admin/pavise/runinject.sh", "10","1","hashmap_tx","1","pgl"],stdout=subprocess.DEVNULL)
    #r.stdout
    fsize = os.path.getsize(path)
    pmfile = open(path,'rb+')
    # Trim file size to working set
    fsize = CUTOFF if fsize > CUTOFF else fsize

    for interval in merged:
        break
        #chunk_offset = random.randrange(size)
        begin = interval[0]
        end = interval[1]
        for i in range(begin,end):
            randn = random.randrange(P)
            #print(randn)
            if(randn == 0):
                inject_one(i - PMEM_BASE,pmfile)
                injectlist.append((i) & ~(CSIZE-1))
                icount += 1
    inject_one(0x7441d0,pmfile)
    pmfile.close()
    cmd = subprocess.Popen(["/home/nvm-admin/pavise/runinject.sh", "10","1","hashmap_tx","0","pgl"],stdout=subprocess.PIPE)
    cmd_out, cmd_err = cmd.communicate(timeout=10)
    if cmd.returncode:
        failcount += 1
    output = cmd_out.decode('utf-8')
    print(output)
    if(cmd_err):
        err = cmd_err.decode('utf-8')
        print(err)
    #sindex = output.find("#s=")
    #findex = output.find("#f=")
    #eindex = output.find("#end")
    #rsuccess = int(output[sindex+3:findex])
    #rfail = int(output[findex+3:eindex])
    #injectset = set(injectlist)

    #print(len(injectset), "injected," ,rsuccess+rfail,"detected,", rsuccess, "success,", rfail, "fail")
    print("injected", icount)
    print("+++++++++++++++++++++++++++++++++++++++++++ iteration",j)
    #if interval[0] - SHADOW_BASE > 0x200000:
        #inject_one(interval[0] - SHADOW_BASE + chunk_offset, pmfile)
        #print("injecting ", interval[0]-SHADOW_BASE)

print("number of crashes:",failcount)

