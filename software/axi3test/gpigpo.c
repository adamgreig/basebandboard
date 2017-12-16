#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/mman.h>

#define FPGA_MANAGER_BASE (0xFF706000)
#define FPGA_MANAGER_SIZE (0x1C)

#define FPGA_MANAGER_STAT       (0x00)
#define FPGA_MANAGER_CTRL       (0x04)
#define FPGA_MANAGER_GPO        (0x10)
#define FPGA_MANAGER_GPI        (0x14)

int main() {
    void *fpga_manager, *status, *control, *gpo, *gpi;
    int fd;

    // Open /dev/mem so we can mmap parts of physical memory into our space
    fd = open("/dev/mem", O_RDWR|O_SYNC);
    if(fd == -1) {
        printf("Error opening /dev/mem\n");
        return 1;
    }

    // Memory map the FPGA manager into our address space
    fpga_manager = mmap(NULL, FPGA_MANAGER_SIZE, PROT_READ|PROT_WRITE,
                        MAP_SHARED, fd, FPGA_MANAGER_BASE);
    if(fpga_manager == MAP_FAILED) {
        printf("Error performing mmap\n");
        close(fd);
        return 1;
    }

    // Get pointers to useful registers
    status = fpga_manager + FPGA_MANAGER_STAT;
    control = fpga_manager + FPGA_MANAGER_CTRL;
    gpo = fpga_manager + FPGA_MANAGER_GPO;
    gpi = fpga_manager + FPGA_MANAGER_GPI;

    uint32_t leds = 0;

    printf("Status     | Control    | GPI        | GPO\n");

    while(true) {
        if(leds++ == 0xFF) {
            leds = 0;
        }
        *(uint32_t*)gpo = leds;

        printf("\r");
        printf("0x%08X | ", *(uint32_t*)status);
        printf("0x%08X | ", *(uint32_t*)control);
        printf("0x%08X | ", *(uint32_t*)gpi);
        printf("0x%08X", *(uint32_t*)gpo);
        fflush(stdout);
        usleep(100000);
    }

    munmap(fpga_manager, FPGA_MANAGER_SIZE);
    close(fd);
    return 0;
}
