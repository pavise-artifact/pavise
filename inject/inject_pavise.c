#include "stdio.h"
#include "stdlib.h"
#include "string.h"
#include "unistd.h"
#include "../include/pavise_interface.h"
#include "fcntl.h"
#include "sys/mman.h"
#include <sys/types.h>
#include <sys/stat.h>
#include "time.h"

#define PMPOOL_SIZE (1024*1024*8)

void inject(int count, char* path){
    int fd = open(path, O_RDWR, S_IRWXU);
    if(fd == -1) {
        printf("error opening file\n");
        return;
    }
    struct stat st;
    if(stat(path, &st)) {
        printf("error getting file size\n");
        return;
    }
    size_t pool_size = st.st_size;

    //posix_fallocate(fd, 0, 1024);
    for (int i = 0 ; i < count; i++){
        unsigned byte_offset = rand() & 0xff;
        byte_offset |= (rand() & 0xff) << 8;
        byte_offset |= (rand() & 0xff) << 16;
        byte_offset |= (rand() & 0xff) << 24; 
        byte_offset = byte_offset % pool_size;
        int bit_offset = rand() % 8;
        lseek(fd, byte_offset, SEEK_SET);
        unsigned char buf;
        read(fd, &buf, 1);
        unsigned char bbuf = buf;
        lseek(fd, byte_offset, SEEK_SET);
        unsigned char mask = 1 << bit_offset;
        unsigned char flip_val = ~(buf & mask);
        buf = buf | mask;
        buf = buf & flip_val;
        write(fd, &buf, 1);
        printf("byte_offset = %u, bit_offset = %d, before = %u, after = %u\n", byte_offset, bit_offset, bbuf, buf);
    }
    //void* ret = mmap(NULL, 512, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    //write(fd, "hello", 6);
    close(fd);
}

int main(int argc, char* argv[]){
    if(argc != 2) {
        printf("input bit flip count as argument\n");
    }
    srand(time(NULL));
    int count = atoi(argv[1]);
    inject(count, "/pmem0p1/pmdk/map");
    inject(count*5, "/pmem0p1/pmdk/map_pavise_pool");
    return 0;
}
