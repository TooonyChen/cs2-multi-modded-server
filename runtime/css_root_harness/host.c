/* The hosting calls CounterStrikeSharp's src/scripting/dotnet_host.cpp makes on Linux. */
#include <dlfcn.h>
#include <stdio.h>
typedef int (*init_fn)(const char *, const void *, void **);
typedef int (*delegate_fn)(void *, int, void **);
typedef int (*load_fn)(const char *, const char *, const char *, const char *, void *, void **);
enum { hdt_load_assembly_and_get_function_pointer = 5 };

int main(int argc, char **argv)
{
    char fxr[4096], config[4096], dll[4096];
    if (argc != 3) return 2;  /* argv[1]: addons/counterstrikesharp root, argv[2]: fxr version */
    snprintf(fxr, sizeof fxr, "%s/dotnet/host/fxr/%s/libhostfxr.so", argv[1], argv[2]);
    snprintf(config, sizeof config, "%s/api/CounterStrikeSharp.API.runtimeconfig.json", argv[1]);
    snprintf(dll, sizeof dll, "%s/api/CounterStrikeSharp.API.dll", argv[1]);
    void *lib = dlopen(fxr, RTLD_LAZY | RTLD_LOCAL);
    if (!lib) { fprintf(stderr, "dlopen: %s\n", dlerror()); return 3; }
    init_fn init = (init_fn)dlsym(lib, "hostfxr_initialize_for_runtime_config");
    delegate_fn get_delegate = (delegate_fn)dlsym(lib, "hostfxr_get_runtime_delegate");
    void *context = 0, *load = 0;
    int (*run)(void) = 0;
    if (!init || !get_delegate || init(config, 0, &context) || !context) return 4;
    if (get_delegate(context, hdt_load_assembly_and_get_function_pointer, &load) || !load) return 5;
    if (((load_fn)load)(dll, "CounterStrikeSharp.API.Bootstrap, CounterStrikeSharp.API", "Run",
                        (const char *)-1 /* UNMANAGEDCALLERSONLY_METHOD */, 0, (void **)&run) || !run) return 6;
    return run();
}
