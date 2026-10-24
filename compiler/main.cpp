// Compile-only JSFX checker. Never call ysfx_init, processing, serialization or GUI APIs.
#include <ysfx.h>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
#ifdef _WIN32
#include <windows.h>
#endif

struct Message { int level; std::string text; };
static std::vector<Message> messages;
static void report(intptr_t, ysfx_log_level level, const char *text) {
    if (messages.size() < 100)
        messages.push_back({static_cast<int>(level), std::string(text).substr(0, 8192)});
}
static void json_string(const std::string &text) {
    std::putchar('"');
    for (unsigned char c : text) {
        if (c == '"' || c == '\\') { std::putchar('\\'); std::putchar(c); }
        else if (c < 32) std::printf("\\u%04x", c);
        else std::putchar(c);
    }
    std::putchar('"');
}
static int run(const char *path) {
    if (std::strcmp(path, "--version") == 0) {
        std::puts("eel2-check 0.5.0 (ysfx 8077347)"); return 0;
    }
    ysfx_config_t *config = ysfx_config_new();
    if (!config) return 2;
    ysfx_set_log_reporter(config, report);
    ysfx_t *effect = ysfx_new(config);
    bool ok = effect && ysfx_load_file(effect, path, 0) && ysfx_compile(effect, 0);
    std::printf("{\"ok\":%s,\"messages\":[", ok ? "true" : "false");
    for (size_t i = 0; i < messages.size(); ++i) {
        if (i) std::putchar(',');
        std::printf("{\"level\":%d,\"text\":", messages[i].level);
        json_string(messages[i].text); std::putchar('}');
    }
    std::puts("]}");
    if (effect) ysfx_free(effect);
    ysfx_config_free(config);
    return ok ? 0 : 1;
}
#ifdef _WIN32
int wmain(int argc, wchar_t **argv) {
    if (argc != 2) return 2;
    int length = WideCharToMultiByte(CP_UTF8, 0, argv[1], -1, nullptr, 0, nullptr, nullptr);
    if (length <= 0) return 2;
    std::vector<char> path(static_cast<size_t>(length));
    WideCharToMultiByte(CP_UTF8, 0, argv[1], -1, path.data(), length, nullptr, nullptr);
    return run(path.data());
}
#else
int main(int argc, char **argv) {
    if (argc != 2) { std::fputs("Usage: eel2-check FILE.jsfx\n", stderr); return 2; }
    return run(argv[1]);
}
#endif
