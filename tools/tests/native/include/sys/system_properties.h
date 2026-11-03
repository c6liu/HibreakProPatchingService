#ifndef TEST_SYSTEM_PROPERTIES_H
#define TEST_SYSTEM_PROPERTIES_H
#define PROP_VALUE_MAX 92
int __system_property_set(const char *name, const char *value);
int __system_property_get(const char *name, char *value);
#endif
