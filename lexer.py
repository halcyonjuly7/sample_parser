import dataclasses
import re
from typing import List, Tuple, Iterable, Optional


class TokenType:
    STRING = "STRING"
    NUMBER = "NUMBER"
    LOGICAL_OR = "LOGICAL_OR"
    LOGICAL_AND = "LOGICAL_AND"
    OPENING_PARENTHESIS = "OPENING_PARENTHESIS"
    CLOSING_PARENTHESIS = "CLOSING_PARENTHESIS"
    OPENING_SQUARE_BRACKET = "OPENING_SQUARE_BRACKET"
    CLOSING_SQUARE_BRACKET = "CLOSING_SQUARE_BRACKET"
    OPENING_CURLY_BRACKET = "OPENING_CURLY_BRACKET"
    CLOSING_CURLY_BRACKET = "CLOSING_CURLY_BRACKET"
    COMPARISON_OPERATOR = "COMPARISON_OPERATOR"
    ADDITIVE_OPERATOR = "ADDITIVE_OPERATOR"
    MULTIPLICATIVE_OPERATOR = "MULTIPLICATIVE_OPERATOR"
    COLON = "COLON"
    KEYWORD = "KEYWORD"
    LOGICAL_OPERATOR = "LOGICAL_OPERATOR"
    COMMA = "COMMA"
    DOT = "DOT"
    IDENTIFIER = "IDENTIFIER"
    EQUALS = "EQUALS"
    EQUALITY = "EQUALITY"
    FILTER = "FILTER"
    MODIFIER = "MODIFIER"
    NULL = "NULL"
    FAT_ARROW = "FAT_ARROW"
    JOINS = "JOINS"
    UNIONS = "UNIONS"
    OVER = "OVER"
    MEMBERSHIP_OPERATOR = "MEMBERSHIP_OPERATOR"



@dataclasses.dataclass
class Token:
    type: str
    value: str




token_spec = [
    (r"\bin\b", TokenType.MEMBERSHIP_OPERATOR),
    (r"=>", TokenType.FAT_ARROW),
    (r":", TokenType.COLON),
    (r"\bor\b", TokenType.LOGICAL_OR),
    (r"\band\b", TokenType.LOGICAL_AND),
    (r">|>=|<|<=|==|!=", TokenType.COMPARISON_OPERATOR),
    (r"\*|\/", TokenType.MULTIPLICATIVE_OPERATOR),
    (r"\+|\-", TokenType.ADDITIVE_OPERATOR),
    (r"==", TokenType.EQUALITY),
    (r"=", TokenType.EQUALS),
    (r"\.", TokenType.DOT),
    (r",", TokenType.COMMA),
    (r"\[", TokenType.OPENING_SQUARE_BRACKET),
    (r"\]", TokenType.CLOSING_SQUARE_BRACKET),
    (r"\(", TokenType.OPENING_PARENTHESIS),
    (r"\)", TokenType.CLOSING_PARENTHESIS),
    (r"\{", TokenType.OPENING_CURLY_BRACKET),
    (r"\}", TokenType.CLOSING_CURLY_BRACKET),
    (r"\bover\b", TokenType.OVER),
    (r"\bleft join\b|\bright join|\bjoin\b|\bunion all\b|\bunion\b", TokenType.JOINS),
    (r"\blet\b|\bdistinct\b|\bwhere\b|\bgroup by\b|\bhaving\b|\bas\b|\bproject\b|\bcount\b|\bfirst\b|\bmatch\b|\bcase\b|\bon\b|\bsum\b|\bpartition by\b", TokenType.KEYWORD),
    (r"\bnull\b", TokenType.NULL),
    (r"\d+", TokenType.NUMBER),
    (r"""['"]\w+['"]""", TokenType.STRING),
    (r"\w+", TokenType.IDENTIFIER),

]


class Lexer:
    def __init__(self, token_spec: List[Tuple[str, str]]):
        self._token_spec = re.compile("|".join([f"(?P<{group}>{reg})" for reg, group in token_spec]))
        self._string = None
        self._tokens = None

    def with_string(self, target: str):
        self._string = target

    def lex(self):
        self._tokens = self._lex()

    def _lex(self) -> Iterable[Token]:
        for matched in self._token_spec.finditer(self._string):
            _type = matched.lastgroup
            value = matched.group()
            yield Token(
                type=_type,
                value=value
            )


    def get_next_token(self) -> Optional[Token]:
        try:
            return next(self._tokens)
        except StopIteration:
            return None
