#include <unistd.h>

void startSideKeyMonitor(void);

int main(void) {
    startSideKeyMonitor();
    for (;;) pause();
}
