#include "tree_sitter/parser.h"
#include <string.h>

enum TokenType { METADATA, SLIDER, IMPORT, SECTION_HEADER, PREPROCESSOR };

void *tree_sitter_eel2_external_scanner_create(void) { return NULL; }
void tree_sitter_eel2_external_scanner_destroy(void *payload) { (void)payload; }
unsigned tree_sitter_eel2_external_scanner_serialize(void *payload, char *buffer) {
  (void)payload; (void)buffer; return 0;
}
void tree_sitter_eel2_external_scanner_deserialize(void *payload, const char *buffer, unsigned length) {
  (void)payload; (void)buffer; (void)length;
}

// Header payloads are free text, including quotes, brackets and comment markers.
// Only recognize them at a line boundary; never inside an EEL2 expression.
bool tree_sitter_eel2_external_scanner_scan(void *payload, TSLexer *lexer, const bool *valid) {
  (void)payload;
  bool line_start = lexer->get_column(lexer) == 0;
  while (lexer->lookahead == ' ' || lexer->lookahead == '\t' ||
         lexer->lookahead == '\r' || lexer->lookahead == '\n') {
    if (lexer->lookahead == '\n') line_start = true;
    lexer->advance(lexer, true);
  }
  if (valid[PREPROCESSOR] && lexer->lookahead == '<') {
    lexer->advance(lexer, false);
    if (lexer->lookahead != '?') return false;
    lexer->advance(lexer, false);
    bool question = false;
    while (!lexer->eof(lexer)) {
      int32_t ch = lexer->lookahead;
      lexer->advance(lexer, false);
      if (question && ch == '>') {
        lexer->result_symbol = PREPROCESSOR;
        return true;
      }
      question = ch == '?';
    }
    lexer->result_symbol = PREPROCESSOR;
    return true;
  }
  if (!line_start) return false;
  enum TokenType token;
  if (lexer->lookahead == '@' && valid[SECTION_HEADER]) {
    token = SECTION_HEADER;
    lexer->advance(lexer, false);
    if (!((lexer->lookahead >= 'a' && lexer->lookahead <= 'z') ||
          (lexer->lookahead >= 'A' && lexer->lookahead <= 'Z'))) return false;
  } else {
    char word[32]; unsigned size = 0;
    while ((lexer->lookahead >= 'a' && lexer->lookahead <= 'z') ||
           (lexer->lookahead >= 'A' && lexer->lookahead <= 'Z') ||
           (lexer->lookahead >= '0' && lexer->lookahead <= '9') || lexer->lookahead == '_') {
      if (size + 1 >= sizeof(word)) return false;
      int32_t ch = lexer->lookahead;
      word[size++] = (char)(ch >= 'A' && ch <= 'Z' ? ch + ('a' - 'A') : ch);
      lexer->advance(lexer, false);
    }
    word[size] = '\0';
    if (!strcmp(word, "import") && valid[IMPORT] &&
        (lexer->lookahead == ' ' || lexer->lookahead == '\t')) {
      token = IMPORT;
    } else if (lexer->lookahead == ':') {
      if (!strncmp(word, "slider", 6) && size > 6 && valid[SLIDER]) {
        for (unsigned i = 6; i < size; ++i) if (word[i] < '0' || word[i] > '9') return false;
        token = SLIDER;
      } else if (valid[METADATA] && (!strcmp(word, "desc") || !strcmp(word, "tags") ||
                 !strcmp(word, "options") || !strcmp(word, "in_pin") ||
                 !strcmp(word, "out_pin") || !strcmp(word, "filename"))) {
        token = METADATA;
      } else return false;
    } else return false;
  }
  while (!lexer->eof(lexer) && lexer->lookahead != '\r' && lexer->lookahead != '\n')
    lexer->advance(lexer, false);
  lexer->result_symbol = token;
  return true;
}
