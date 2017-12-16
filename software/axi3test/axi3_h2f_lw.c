#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/mman.h>

#define H2F_LW_BASE     (0xFF200000)
#define H2F_LW_SIZE     (0x00200000)

int main() {
    void *h2f_lw, *reg0, *reg1, *reg2, *reg3;
    int fd;

    // Open /dev/mem so we can mmap parts of physical memory into our space
    fd = open("/dev/mem", O_RDWR|O_SYNC);
    if(fd == -1) {
        printf("Error opening /dev/mem\n");
        return 1;
    }

    // Memory map the bridge into our address space
    h2f_lw = mmap(NULL, H2F_LW_SIZE, PROT_READ|PROT_WRITE, MAP_SHARED,
                  fd, H2F_LW_BASE);
    if(h2f_lw == MAP_FAILED) {
        printf("Error performing mmap\n");
        close(fd);
        return 1;
    }

    // Get pointers to our registers
    reg0 = h2f_lw + 0;
    reg1 = h2f_lw + 4;
    reg2 = h2f_lw + 8;
    reg3 = h2f_lw + 12;

    uint32_t leds = 0;

    printf("Reg0       | Reg1       | Reg2       | Reg3\n");

    while(true) {
        if(leds++ == 0xFF) {
            leds = 0;
        }
        *(uint32_t*)reg0 = leds;

        uint32_t r0, r1, r2, r3;
        r0 = *(uint32_t*)reg0;
        r1 = *(uint32_t*)reg1;
        r2 = *(uint32_t*)reg2;
        r3 = *(uint32_t*)reg3;
        printf("\r");
        printf("0x%08X | ", r0);
        printf("0x%08X | ", r1);
        printf("0x%08X | ", r2);
        printf("0x%08X", r3);
        fflush(stdout);
        usleep(10000);
    }

    munmap(h2f_lw, H2F_LW_SIZE);
    close(fd);
    return 0;
}
