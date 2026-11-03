#include <dlfcn.h>
#include <hardware/consumerir.h>
#include <stdio.h>
#include <string.h>

int main(int argc, char **argv) {
    if (argc != 2) {
        fprintf(stderr, "Usage: %s <consumerir-module.so>; queries only, NEVER transmits\n", argv[0]);
        return 2;
    }
    void *library = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (!library) {
        fprintf(stderr, "dlopen: %s\n", dlerror());
        return 1;
    }
    consumerir_module_t *module = dlsym(library, HAL_MODULE_INFO_SYM_AS_STR);
    if (!module || module->common.tag != HARDWARE_MODULE_TAG ||
        strcmp(module->common.id, CONSUMERIR_HARDWARE_MODULE_ID) != 0 ||
        !module->common.methods || !module->common.methods->open) {
        fprintf(stderr, "Invalid consumerir module ABI\n");
        dlclose(library);
        return 1;
    }
    hw_device_t *common = NULL;
    int result = module->common.methods->open(&module->common, CONSUMERIR_TRANSMITTER, &common);
    if (result || !common) {
        fprintf(stderr, "HAL open failed: %d\n", result);
        dlclose(library);
        return 1;
    }
    consumerir_device_t *device = (consumerir_device_t *)common;
    consumerir_freq_range_t ranges[2];
    int count = device->get_num_carrier_freqs(device);
    int filled = device->get_carrier_freqs(device, 2, ranges);
    result = count == 2 && filled == 2 && ranges[0].min == 38000 && ranges[0].max == 38000 &&
             ranges[1].min == 38222 && ranges[1].max == 38222 ? 0 : 1;
    if (result)
        fprintf(stderr, "Unexpected frequency query: count=%d filled=%d\n", count, filled);
    else
        printf("PASS: module ABI, device open, 38000/38222 Hz aliases. No transmission performed.\n");
    if (common->close(common) != 0 || dlclose(library) != 0)
        result = 1;
    return result;
}
