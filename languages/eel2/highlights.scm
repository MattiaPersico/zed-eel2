(comment) @comment
(string) @string
(number) @number
(identifier) @variable
(string_identifier) @variable
(function_def name: (identifier) @function)
(function_call name: (identifier) @function)
["function" "while" "local" "static" "instance" "global" "globals"] @keyword
["(" ")" "[" "]"] @punctuation.bracket
[";" ","] @punctuation.delimiter
(metadata) @attribute
(slider) @property
(import) @keyword
(section_header) @keyword
(preprocessor) @preproc
(namespace_parameter) @variable.parameter
