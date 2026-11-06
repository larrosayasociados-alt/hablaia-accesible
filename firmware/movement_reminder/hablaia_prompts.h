#ifndef HABLAIA_PROMPTS_H_
#define HABLAIA_PROMPTS_H_

#include <stddef.h>
#include <stdint.h>
#include <string_view>

extern "C" {
extern const uint8_t hablaia_mover_0_ogg[];
extern const unsigned hablaia_mover_0_ogg_len;
extern const uint8_t hablaia_mover_1_ogg[];
extern const unsigned hablaia_mover_1_ogg_len;
extern const uint8_t hablaia_mover_2_ogg[];
extern const unsigned hablaia_mover_2_ogg_len;
extern const uint8_t hablaia_mover_3_ogg[];
extern const unsigned hablaia_mover_3_ogg_len;
}

inline std::string_view HablaiaPromptOgg(int index) {
    const uint8_t* data = hablaia_mover_0_ogg;
    unsigned length = hablaia_mover_0_ogg_len;
    if (index == 1) {
        data = hablaia_mover_1_ogg;
        length = hablaia_mover_1_ogg_len;
    } else if (index == 2) {
        data = hablaia_mover_2_ogg;
        length = hablaia_mover_2_ogg_len;
    } else if (index == 3) {
        data = hablaia_mover_3_ogg;
        length = hablaia_mover_3_ogg_len;
    }
    return std::string_view(reinterpret_cast<const char*>(data), static_cast<size_t>(length));
}

#endif
