#ifndef HIBREAK_CLIENT_AUTH_H
#define HIBREAK_CLIENT_AUTH_H

#include <stdio.h>
#include <sys/types.h>

int hibreak_package_uid_matches(FILE *packages, uid_t uid);
int hibreak_authorize_client(int socket_fd);

#endif
