// Derived from DyGriin/tree-sitter-eel2, revision 97d4ad9b26390fe7c255d36765eda09a2b1ed73c.
// JSFX structure and regression fixes: Copyright 2026 Mattia Persico. See LICENSE.

// references:
// https://github.com/justinfrankel/WDL/blob/main/WDL/eel2/eel2.l
// https://github.com/justinfrankel/WDL/blob/main/WDL/eel2/eel2.y
// https://github.com/justinfrankel/WDL/blob/main/WDL/eel2/nseel-compiler.c#L4681
// https://github.com/justinfrankel/WDL/blob/main/WDL/eel2/nseel-eval.c

const PREC = {
    STATEMENT: 0,
    ASSIGN: 1,
    CONDITIONAL: 2,
    LOGICAL: 3,
    COMPARE: 4,
    BITWISE: 5,
    ADD: 6,
    SUB: 7,
    MUL: 8,
    DIV: 9,
    MOD: 10,
    POW: 11,
    UNARY: 12,
};

module.exports = grammar({
    name: "eel2",

    extras: $ => [$.comment, $.preprocessor, /\s/],

    externals: $ => [$.metadata, $.slider, $.import, $.section_header, $.preprocessor],

    conflicts: $ => [[$.program, $._top_level_statement]],

    supertypes: $ => [
        $._expression
    ],

    rules: {
        program: $ => seq(
            repeat(choice($.metadata, $.slider, $.import)),
            optional(choice(repeat1($.section), $.section_body))
        ),
        section: $ => seq(
            field("name", $.section_header),
            optional(field("body", $.section_body))
        ),
        section_body: $ => choice(
            seq(repeat1($._top_level_statement), optional($._top_level_last)),
            $._top_level_last
        ),
        _top_level_statement: $ => choice(
            $.function_def,
            $.import,
            $._statement
        ),
        _top_level_last: $ => $._expression,

        // FUNCTION
        function_def: $ => seq(
            alias($._function_word, "function"),
            field("name", $.identifier),
            choice(
                seq($.parameter_list, repeat($._context_table)),
                seq(repeat1($._context_table))
            ),
            field("body", $.parenthesized),
        ),

        _context_table: $ => choice(
            $.global_table,
            $.local_table,
            $.instance_table
        ),
        global_table: $ => seq(
            choice("global", "globals"), $.parameter_list
        ),
        local_table: $ => seq(
            choice("local", "static"), $.parameter_list
        ),
        instance_table: $ => seq(
            "instance", $.parameter_list
        ),
        parameter_list: $ => seq(
            "(", repeat(choice(
                $.identifier,
                $.namespace_parameter,
                "*",
                ",")),
            ")"
        ),

        namespace_parameter: $ => prec(1, seq($.identifier, "*")),

        // STATEMENTS
        _statement: $ => seq(
            optional($._expression), ";"
        ),

        // EXPRESSIONS
        _expression: $ => choice(
            $.assignment,
            $.unary,
            $.binary,
            $.conditional,
            $._rvalue_expr,
        ),

        assignment: $ => prec.right(PREC.ASSIGN, seq(
            field("lhs", $._lvalue_expr),
            field("op", choice(
                "=", "+=", "-=", "*=", "/=", "%=", "^=",
                "|=", "&=", "~="
            )),
            field("rhs", $._expression),
        )),

        unary: $ => prec(PREC.UNARY, seq(
            field("op", choice("+", "-", "!")),
            field("rhs", $._expression),
        )),

        binary: $ => choice(
            ...[
                [PREC.LOGICAL, "&&", "||"],
                [PREC.COMPARE, "<", ">", "<=", ">=", "==", "===", "!=", "!=="],
                [PREC.BITWISE, "&", "|", "~"],
                [PREC.ADD, "+"],
                [PREC.SUB, "-"],
                [PREC.MUL, "*"],
                [PREC.DIV, "/"],
                [PREC.MOD, "%", ">>", "<<"],
                [PREC.POW, "^"]
            ].reduce((table, [precedence, ...ops]) => {
                table.push(...ops.map((operator) =>
                    prec.left(precedence, seq(
                        field("lhs", $._expression),
                        field("op", operator),
                        field("rhs", $._expression),
                    )
                )));
                return table
            }, [])
        ),

        conditional: $ => prec.right(PREC.CONDITIONAL, choice(
            seq(field("cond", $._expression), "?",
                optional(field("then", $._expression)),
                ":", field("else", $._expression)),
            seq(field("cond", $._expression), "?",
                field("then", $._expression)),
        )),

        _rvalue_expr: $ => choice(
            $._lvalue_expr,
            $.number,
            $.string,
            $.chained_string,
        ),

        _lvalue_expr: $ => choice(
            $.identifier,
            $.string_identifier,
            $.parenthesized,
            $.function_call,
            $.while,
            $.index
        ),

        parenthesized: $ => seq(
            "(", optional($._inblock), ")"
        ),
        _inblock: $ => seq(
            $._expression, optional($._more_inblock)
        ),
        _more_inblock: $ => seq(
            ";", repeat($._statement), optional($._expression)
        ),

        function_call: $ => seq(
            field("name", $.identifier),
            field("args", $.argument_list)
        ),

        argument_list: $ => seq(
            "(",
            optional(seq(
                $.argument,
                repeat(seq(",", $.argument))
            )),
            ")"
        ),
        argument: $ => $._inblock,

        while: $ => prec(1, seq(  // higher precedence than $.function_call
            alias($._while_word, "while"),
            optional(field("cond", $.parenthesized)),
            field("body", $.parenthesized),
        )),

        index: $ => seq(
            field("start", $._rvalue_expr),
            "[",
            optional(field("index", $.argument)),
            "]"
        ),

        // IDENTIFIERS
        identifier: $ => choice(
            $._identifier,
            $._identifier_from_keyword
        ),

        _identifier: $ => /[a-zA-Z_][a-zA-Z0-9\._]*/,
        _identifier_from_keyword: $ => choice(
            $._function_word,
            $._while_word
        ),
        _function_word: $ => "function",
        _while_word: $ => "while",

        string_identifier: $ => /#[a-zA-Z0-9\._]*/,

        // LITERALS
        number: $ => token(choice(
            /(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?/,
            /[$0][xX][0-9a-fA-F]*/,
            /\$\~\d*/,
            /\$'.'/,
            /\$[Ee]/,
            /\$[Pp][Ii]/,
            /\$[Pp][Hh][Ii]/,
            /'([^'\\]|\\.)*'/,
        )),

        chained_string: $ => seq(
            $.string, repeat1($.string)
        ),

        string: $ => /"([^"\\]|\\.)*"/,

        comment: $ => token(choice(
            seq("//", /[^\r\n]*/),
            seq("/*", /[^*]*\*+([^/*][^*]*\*+)*/, "/")
        )),
    },
})
