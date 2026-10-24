#!/usr/bin/env python3
"""Generate syntaxes/lcl.tmLanguage.json.

The JSON is the artifact VS Code loads; this script is where the word
rules and keyword lists live, so the regex escaping stays correct and the
lists can be diffed against tree-sitter-lcl/queries/highlights.scm.

    python3 scripts/build-grammar.py syntaxes/lcl.tmLanguage.json
"""
import json, re, sys

OUT = sys.argv[1]

# Word boundaries: Lcl words end at whitespace, ';', newline, ']' and, by
# the same grammar choice tree-sitter-lcl makes, at '[ " { } ( )'.
D = r'\s;\[\]{}()"'
WS = rf'(?<![^{D}])'   # preceded by a delimiter or line start
WE = rf'(?![^{D}])'    # followed by a delimiter or line end
WORD = rf'[^{D}]+'
NAME = rf'(?![$@,])[^{D}]+'          # a binding name (not $var, @spread, ,unquote)
HEAD = r'(?:^|(?<=[;\[{]))\s*'       # position of a command's first word
QUAL = r'(?:(?:::)[A-Za-z_][A-Za-z0-9_?!-]*(?:::[A-Za-z_][A-Za-z0-9_?!-]*)*|[A-Za-z_][A-Za-z0-9_?!-]*(?:::[A-Za-z_][A-Za-z0-9_?!-]*)+)'

def words(ws):
    return '(?:' + '|'.join(sorted((re.escape(w) for w in ws), key=len, reverse=True)) + ')'

def word_rule(scope, ws):
    return {'name': scope, 'match': WS + words(ws) + WE}

KEYWORD_RULES = [
    word_rule('keyword.control.conditional.lcl', ['if', 'else', 'cond', 'case']),
    word_rule('keyword.control.loop.lcl', ['while', 'for', 'foreach', 'repeat', 'break', 'continue']),
    word_rule('keyword.control.return.lcl', ['return']),
    word_rule('keyword.control.import.lcl', ['import', 'load', 'require']),
    word_rule('storage.type.function.lcl', ['proc', 'lambda', 'macro']),
    word_rule('storage.type.lcl', ['let', 'var', 'set!']),
    word_rule('storage.type.namespace.lcl', ['namespace']),
    word_rule('keyword.control.lcl', ['catch', 'isolate']),
    word_rule('keyword.other.eval.lcl', ['eval', 'eval_at', 'subst', 'quasiquote', 'macroexpand']),
    word_rule('keyword.operator.logical.lcl', ['and', 'or', 'not']),
]

BUILTINS = ['puts', 'list', 'dict', 'len', 'get', 'put', 'del', 'put!', 'del!',
    'has?', 'empty?', 'ref', 'repr', 'type', 'apply', 'arity', 'getvar', 'gensym',
    'error', 'exit', 'assert', 'assert_eq', 'assert_neq',
    'int', 'float', 'int?', 'float?', 'number?', 'string?', 'list?', 'dict?',
    'proc?', 'cell?', 'opaque?', 'same?', 'not-same?',
    'binding-cell', 'same-binding?']

OPERATORS = ['+', '-', '*', '/', '%', '==', '!=', '<', '>', '<=', '>=', '->', '->>']

INT = r'(?:0|-?[1-9][0-9]*)'
FLOAT = r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+(?:[eE][+-]?[0-9]+)?|[eE][+-]?[0-9]+)'

def head_rule(scope_kw, kw, scope_name, extra=''):
    return {
        'match': HEAD + rf'({kw})\s+({NAME})' + extra,
        'captures': {'1': {'name': scope_kw}, '2': {'name': scope_name}},
    }

grammar = {
    '$schema': 'https://raw.githubusercontent.com/martinring/tmlanguage/master/tmlanguage.json',
    'name': 'Lcl',
    'scopeName': 'source.lcl',
    'fileTypes': ['lcl'],
    'patterns': [{'include': '#statements-top'}],
    'repository': {

        # ---- statement contexts -------------------------------------------
        'statements-top': {
            'comment': 'Top level: comments run to end of line regardless of delimiters.',
            'patterns': [
                {'include': '#comment-top'},
                {'include': '#statement'},
            ],
        },
        'statements': {
            'comment': 'Inside a brace or bracket word: Lcl finds the word extent before it looks for comments, so an unbalanced } in a comment closes the block.',
            'patterns': [
                {'include': '#comment-nested'},
                {'include': '#statement'},
            ],
        },
        'statement': {
            'patterns': [
                {'include': '#definitions'},
                {'include': '#command-head'},
                {'include': '#words'},
            ],
        },

        # ---- words (anything that is not a command head) ------------------
        'words': {
            'patterns': [
                {'include': '#continuation'},
                {'include': '#escape'},
                {'include': '#string'},
                {'include': '#dict'},
                {'include': '#block'},
                {'include': '#subcommand'},
                {'include': '#list'},
                {'include': '#variable'},
                {'include': '#number'},
                {'include': '#prefix'},
                {'include': '#keywords'},
                {'include': '#builtins'},
                {'include': '#operators'},
                {'include': '#qualified-name'},
            ],
        },
        'list-words': {
            'comment': 'Contents of (...) and #{...}: words, never commands; newlines are whitespace.',
            'patterns': [
                {'include': '#comment-nested'},
                {'include': '#words'},
            ],
        },

        # ---- comments -----------------------------------------------------
        'comment-top': {
            'patterns': [
                {'name': 'comment.line.documentation.lcl', 'match': '(;;;).*$',
                 'captures': {'1': {'name': 'punctuation.definition.comment.lcl'}}},
                {'name': 'comment.line.double-semicolon.lcl', 'match': '(;;).*$',
                 'captures': {'1': {'name': 'punctuation.definition.comment.lcl'}}},
            ],
        },
        'comment-nested': {
            'patterns': [
                {'name': 'comment.line.documentation.lcl', 'begin': ';;;', 'end': r'$|(?=\})',
                 'beginCaptures': {'0': {'name': 'punctuation.definition.comment.lcl'}},
                 'patterns': [{'include': '#comment-braces'}]},
                {'name': 'comment.line.double-semicolon.lcl', 'begin': ';;', 'end': r'$|(?=\})',
                 'beginCaptures': {'0': {'name': 'punctuation.definition.comment.lcl'}},
                 'patterns': [{'include': '#comment-braces'}]},
            ],
        },
        'comment-braces': {
            'comment': 'Balanced braces inside a nested comment do not close the enclosing block.',
            'begin': r'\{', 'end': r'\}',
            'patterns': [{'include': '#comment-braces'}],
        },

        # ---- strings ------------------------------------------------------
        'string': {
            'comment': 'A "..." template. It also ends before an unbalanced }, which is what Lcl\'s brace-depth rule does to a quote inside a brace word.',
            'name': 'string.quoted.double.lcl',
            'begin': '"', 'end': r'"|(?=\})',
            'beginCaptures': {'0': {'name': 'punctuation.definition.string.begin.lcl'}},
            'endCaptures': {'0': {'name': 'punctuation.definition.string.end.lcl'}},
            'patterns': [{'include': '#string-body'}],
        },
        'string-body': {
            'patterns': [
                {'include': '#continuation'},
                {'include': '#escape'},
                {'include': '#variable'},
                {'include': '#subcommand'},
                {'include': '#string-braces'},
            ],
        },
        'string-braces': {
            'comment': 'Balanced braces inside a string are plain text that keeps the brace depth even.',
            'begin': r'\{', 'end': r'\}|(?=")',
            'patterns': [{'include': '#string-body'}],
        },
        'escape': {
            'name': 'constant.character.escape.lcl',
            'match': r'\\(?:x[0-9A-Fa-f]{1,2}|[0-7]{1,3}|.)',
        },
        'continuation': {
            'name': 'punctuation.separator.continuation.lcl',
            'match': r'\\$',
        },

        # ---- compound words -----------------------------------------------
        'block': {
            'name': 'meta.block.lcl',
            'begin': r'\{', 'end': r'\}',
            'beginCaptures': {'0': {'name': 'punctuation.section.block.begin.lcl'}},
            'endCaptures': {'0': {'name': 'punctuation.section.block.end.lcl'}},
            'patterns': [{'include': '#statements'}],
        },
        'subcommand': {
            'comment': 'Also ends before an unbalanced }: a brace word\'s extent is decided by brace depth alone.',
            'name': 'meta.subcommand.lcl',
            'begin': r'\[', 'end': r'\]|(?=\})',
            'beginCaptures': {'0': {'name': 'punctuation.section.brackets.begin.lcl'}},
            'endCaptures': {'0': {'name': 'punctuation.section.brackets.end.lcl'}},
            'patterns': [{'include': '#statements'}],
        },
        'list': {
            'name': 'meta.list.lcl',
            'begin': r'\(', 'end': r'\)|(?=\})',
            'beginCaptures': {'0': {'name': 'punctuation.section.parens.begin.lcl'}},
            'endCaptures': {'0': {'name': 'punctuation.section.parens.end.lcl'}},
            'patterns': [{'include': '#list-words'}],
        },
        'dict': {
            'name': 'meta.dict.lcl',
            'begin': WS + r'#\{', 'end': r'\}',
            'beginCaptures': {'0': {'name': 'punctuation.section.dict.begin.lcl'}},
            'endCaptures': {'0': {'name': 'punctuation.section.dict.end.lcl'}},
            'patterns': [{'include': '#list-words'}],
        },

        # ---- atoms --------------------------------------------------------
        'variable': {
            'patterns': [
                {'name': 'variable.other.lcl',
                 'match': r'(\$)([A-Za-z_][A-Za-z0-9_]*)',
                 'captures': {'1': {'name': 'punctuation.definition.variable.lcl'}}},
                {'name': 'variable.other.qualified.lcl',
                 'match': r'(\$\{)((?:::)?[A-Za-z_][A-Za-z0-9_?!-]*(?:::[A-Za-z_][A-Za-z0-9_?!-]*)*)(\})',
                 'captures': {'1': {'name': 'punctuation.definition.variable.begin.lcl'},
                              '3': {'name': 'punctuation.definition.variable.end.lcl'}}},
                {'name': 'invalid.illegal.variable.lcl',
                 'match': r'\$\{[^}\s]*\}'},
            ],
        },
        'number': {
            'patterns': [
                {'name': 'constant.numeric.float.lcl', 'match': WS + FLOAT + WE},
                {'name': 'constant.numeric.integer.lcl', 'match': WS + INT + WE},
            ],
        },
        'prefix': {
            'patterns': [
                # @ also follows an unquote marker: ,@$xs splices a list
                {'name': 'keyword.operator.spread.lcl', 'match': r'(?<![^\s;\[\]{}()",])@'},
                {'name': 'keyword.operator.unquote.lcl', 'match': WS + rf',,?(?![{D}]|$)'},
            ],
        },
        'keywords': {'patterns': KEYWORD_RULES},
        'builtins': {'patterns': [word_rule('support.function.builtin.lcl', BUILTINS)]},
        'operators': {'patterns': [word_rule('keyword.operator.lcl', OPERATORS)]},
        'qualified-name': {
            'name': 'entity.name.function.qualified.lcl',
            'match': WS + QUAL + WE,
        },

        # ---- commands -----------------------------------------------------
        'command-head': {
            'comment': 'The first word of a command (line start, after ;, [ or {) is a call unless it is a keyword, builtin, operator or number.',
            'match': HEAD + rf'((?!\$[A-Za-z_{{])(?!#\{{)(?![@,\\])[^{D}$]+)',
            'captures': {'1': {'patterns': [
                {'include': '#keywords'},
                {'include': '#builtins'},
                {'include': '#operators'},
                {'include': '#number'},
                {'include': '#qualified-name'},
                {'name': 'entity.name.function.call.lcl', 'match': '.+'},
            ]}},
        },
        'definitions': {
            'patterns': [
                # proc name {params} ...
                {'name': 'meta.function.lcl',
                 'begin': HEAD + rf'(proc|macro)\s+({NAME})\s*(\{{)',
                 'end': r'\}',
                 'beginCaptures': {'1': {'name': 'storage.type.function.lcl'},
                                   '2': {'name': 'entity.name.function.lcl'},
                                   '3': {'name': 'punctuation.section.parameters.begin.lcl'}},
                 'endCaptures': {'0': {'name': 'punctuation.section.parameters.end.lcl'}},
                 'contentName': 'meta.function.parameters.lcl',
                 'patterns': [{'include': '#parameters'}]},
                head_rule('storage.type.function.lcl', 'proc|macro', 'entity.name.function.lcl'),
                # lambda {params} ...
                {'name': 'meta.function.lambda.lcl',
                 'begin': HEAD + r'(lambda)\s*(\{)',
                 'end': r'\}',
                 'beginCaptures': {'1': {'name': 'storage.type.function.lcl'},
                                   '2': {'name': 'punctuation.section.parameters.begin.lcl'}},
                 'endCaptures': {'0': {'name': 'punctuation.section.parameters.end.lcl'}},
                 'contentName': 'meta.function.parameters.lcl',
                 'patterns': [{'include': '#parameters'}]},
                head_rule('storage.type.lcl', 'let|var|set!', 'variable.other.definition.lcl'),
                head_rule('keyword.control.loop.lcl', 'foreach', 'variable.other.definition.lcl'),
                head_rule('storage.type.namespace.lcl', 'namespace', 'entity.name.namespace.lcl'),
                head_rule('keyword.control.import.lcl', 'import', 'entity.name.namespace.lcl'),
            ],
        },
        'parameters': {
            'patterns': [
                {'include': '#comment-nested'},
                {'include': '#continuation'},
                # (name default)
                {'name': 'meta.parameter.optional.lcl',
                 'begin': rf'(\()\s*({NAME})', 'end': r'\)',
                 'beginCaptures': {'1': {'name': 'punctuation.section.parens.begin.lcl'},
                                   '2': {'name': 'variable.parameter.lcl'}},
                 'endCaptures': {'0': {'name': 'punctuation.section.parens.end.lcl'}},
                 'patterns': [{'include': '#words'}]},
                {'name': 'variable.parameter.lcl', 'match': WORD},
            ],
        },
    },
}

with open(OUT, 'w') as f:
    json.dump(grammar, f, indent=2, ensure_ascii=False)
    f.write('\n')
print('wrote', OUT)
