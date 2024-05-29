import json
import re
from typing import Dict, Callable

from lexer import Lexer, Token, TokenType, token_spec


class Parser:
    def __init__(self, lexer: Lexer):
        self._lexer = lexer
        self._tokens = None
        self._lookahead = None

    def parse(self, target):
        self._lexer.with_string(target)
        self._lexer.lex()
        self._lookahead = self._lexer.get_next_token()
        return self.statement_list()

    def statement_list(self) -> Dict:
        statements = []
        while self._lookahead:
            statements.append(self.statement())

        return {
            "type": "StatementList",
            "body": statements
        }

    def statement(self) -> Dict:
        if self._lookahead.value == "let":
            return self.variable_assignment_statement()
        if self._lookahead.type == TokenType.OPENING_CURLY_BRACKET:
            return self.block_statement()
        if self._lookahead.value in ("where", "having", "group by"):
            return self.filter_statement_list()
        if self._lookahead.type == TokenType.IDENTIFIER:
            return self.column_assignment_list()
        return self.expression()

    def variable_assignment_statement(self) -> Dict:
        self._consume(TokenType.KEYWORD)
        name = self._consume(TokenType.IDENTIFIER).value
        self._consume(TokenType.EQUALS)

        if self._lookahead.type == TokenType.OPENING_CURLY_BRACKET:
            value = self.statement()
        else:
            value = self.expression()

        return {
            "type": "VariableAssignment",
            "name": name,
            "value": value
        }

    def filter_statement_list(self) -> Dict:
        _filter = [self.filter_statement()]
        while self._lookahead.value in ("group by", "having", "where"):
            _filter.append(self.filter_statement())
        return {
            "type": "FilterStatementList",
            "body": _filter
        }

    def filter_statement(self) -> Dict:
        _filter = self._consume(TokenType.KEYWORD)
        return {
            "type": "filter",
            "value": _filter.value,
            "body": self.statement() if _filter.value == "group by" else self.expression()
        }

    def block_statement(self) -> Dict:
        self._consume(TokenType.OPENING_CURLY_BRACKET)
        modifier = self._consume(TokenType.KEYWORD).value if self._lookahead.type == TokenType.KEYWORD else None
        statements = []
        while self._lookahead.type != TokenType.CLOSING_CURLY_BRACKET:
            statements.append(self.statement())
        self._consume(TokenType.CLOSING_CURLY_BRACKET)
        return {
            "type": "BlockStatement",
            "modifier": modifier,
            "body": statements
        }

    def column_assignment_list(self) -> Dict:
        assignments = [self.column_assignment_statement()]
        while self._lookahead.type == TokenType.COMMA:
            self._consume(TokenType.COMMA)
            assignments.append(self.column_assignment_statement())
        return {
            "type": "ColumnAssignmentList",
            "body": assignments
        }

    def column_assignment_statement(self) -> Dict:
        name = self.expression()
        if self._lookahead.type == TokenType.COLON:
            self._consume(TokenType.COLON)
            value = self.expression()
            return {
                "type": "ColumnAssignmentStatement",
                "name": name,
                "value": value
            }
        return name

    def project_expression(self) -> Dict:
        self._consume(TokenType.KEYWORD)
        self._consume(TokenType.IDENTIFIER)
        self._consume(TokenType.KEYWORD)
        body = self.statement()
        return {
            "type": "ProjectExpression",
            "body": body
        }

    def parenthesized_expression(self) -> Dict:
        self._consume(TokenType.OPENING_PARENTHESIS)
        body = self.expression()
        self._consume(TokenType.CLOSING_PARENTHESIS)
        return {
            "type": "ParenthesizedExpression",
            "body": body
        }

    def match_expression(self) -> Dict:
        self._consume(TokenType.KEYWORD)
        cases = []
        self._consume(TokenType.OPENING_CURLY_BRACKET)
        while self._lookahead.type != TokenType.CLOSING_CURLY_BRACKET:
            cases.append(self.case_expression())
        self._consume(TokenType.CLOSING_CURLY_BRACKET)
        return {
            "type": "MatchExpression",
            "body": cases
        }

    def case_expression(self) -> Dict:
        self._consume(TokenType.KEYWORD)
        condition = self.expression()
        self._consume(TokenType.FAT_ARROW)
        value = self.expression()
        return {
            "type": "CaseExpression",
            "conditions": condition,
            "value": value
        }

    def functional_expression(self) -> Dict:
        name = self._consume(TokenType.KEYWORD).value
        self._consume(TokenType.OPENING_PARENTHESIS)
        args = [self.expression()]
        while self._lookahead.type == TokenType.COMMA:
            self._consume(TokenType.COMMA)
            args.append(self.expression())
        self._consume(TokenType.CLOSING_PARENTHESIS)
        return {
            "type": "FunctionalExpression",
            "name": name,
            "args": args
        }

    def literals(self) -> Dict:
        if self._lookahead.type == TokenType.STRING:
            return self.string_literal()

        if self._lookahead.type == TokenType.NUMBER:
            return self.numeric_literal()

        return self.null_literal()

    def string_literal(self) -> Dict:
        value = self._consume(TokenType.STRING).value
        return {
            "type": "StringLiteral",
            "value": re.search(r"""[^'"]+""", value).group()
        }

    def numeric_literal(self) -> Dict:
        value = self._consume(TokenType.NUMBER).value
        return {
            "type": "NumericLiteral",
            "value": int(value)
        }

    def null_literal(self) -> Dict:
        self._consume(TokenType.NULL)
        return {
            "type": "NULL",
            "value": None
        }

    def expression(self) -> Dict:
        return self.over_expression()

    def over_expression(self):
        return self.binary_expression(self.join_expr, TokenType.OVER)

    def join_expr(self):
        return self.union_join_expression(self.logical_or)

    def logical_or(self) -> Dict:
        return self.binary_expression(self.logical_and, TokenType.LOGICAL_OR)

    def logical_and(self) -> Dict:
        return self.binary_expression(self.equality_expression, TokenType.LOGICAL_AND)

    def equality_expression(self) -> Dict:
        return self.binary_expression(self.relational_expression, TokenType.EQUALITY)

    def relational_expression(self) -> Dict:
        return self.binary_expression(self.additive_expression, TokenType.COMPARISON_OPERATOR)

    def additive_expression(self) -> Dict:
        return self.binary_expression(self.multiplicative_expression, TokenType.ADDITIVE_OPERATOR)

    def multiplicative_expression(self) -> Dict:
        return self.binary_expression(self.membership_expression, TokenType.MULTIPLICATIVE_OPERATOR)

    def membership_expression(self) -> Dict:
        return self.binary_expression(self.unary_expression, TokenType.MEMBERSHIP_OPERATOR, type="MembershipExpression")

    def unary_expression(self) -> Dict:
        operator = None
        if self._lookahead.type == TokenType.ADDITIVE_OPERATOR:
            operator = self._consume(TokenType.ADDITIVE_OPERATOR).value

        if operator:
            return {
                "type": "unary_expression",
                "operator": operator,
                "argument": self.primary_expression()
            }
        return self.primary_expression()

    def union_join_expression(self, func: Callable) -> Dict:
        left = func()
        while self._lookahead and self._lookahead.type == TokenType.JOINS:
            join_type = self._consume(TokenType.JOINS).value
            right = func()
            if "join" in join_type:
                self._consume(TokenType.KEYWORD)
                cond = func()
                left = {
                    "type": "JoinExpression",
                    "join_type": join_type,
                    "left": left,
                    "right": right,
                    "condition": cond
                }
            else:
                left = {
                    "type": "UnionExpression",
                    "left": left,
                    "right": right
                }
        return left

    def primary_expression(self) -> Dict:
        if self._lookahead.type == TokenType.IDENTIFIER:
            return self.identifier_expression()
        if self._lookahead.value == "match":
            return self.match_expression()
        if self._lookahead.value == "case":
            return self.case_expression()
        if self._lookahead.value == "project":
            return self.project_expression()
        if self._lookahead.value == "partition by":
            return self.partition_by_expression()
        if self._lookahead.type == TokenType.KEYWORD:
            return self.functional_expression()
        if self._lookahead.type == TokenType.OPENING_PARENTHESIS:
            return self.parenthesized_expression()
        if self._lookahead.type == TokenType.OPENING_SQUARE_BRACKET:
            return self.array_expression()
        return self.literals()

    def partition_by_expression(self) -> Dict:
        self._consume(TokenType.KEYWORD)
        body = [self.expression()]
        while self._lookahead.type == TokenType.COMMA:
            self._consume(TokenType.COMMA)
            body.append(self.expression())
        return {
            "type": "PartitionByExpression",
            "body": body
        }

    def identifier_expression(self) -> Dict:
        _id = [self._consume(TokenType.IDENTIFIER).value]
        while self._lookahead and self._lookahead.type == TokenType.DOT:
            self._consume(TokenType.DOT)
            _id.append(self._consume(TokenType.IDENTIFIER).value)
        res = {
            "type": "IdentifierExpression",
            "value": ".".join(_id)
        }
        if len(_id) > 1:
            res["source_table"] = _id[0]
        return res

    def binary_expression(self, func: Callable, token_type: str, type: str = "BinaryExpression"):
        left = func()
        while self._lookahead and self._lookahead.type == token_type:
            op = self._consume(token_type).value
            right = func()
            left = {
                "type": type,
                "operator": op,
                "left": left,
                "right": right
            }
        return left

    def array_expression(self) -> Dict:
        self._consume(TokenType.OPENING_SQUARE_BRACKET)
        items = []
        while self._lookahead.type != TokenType.CLOSING_SQUARE_BRACKET:
            items.append(self.literals())

        self._consume(TokenType.CLOSING_SQUARE_BRACKET)

        return {
            "type": "ArrayExpression",
            "body": items
        }

    def _consume(self, token_type: str) -> Token:

        if self._lookahead.type != token_type:
            raise SyntaxError(f"Unexpected token {token_type}")

        if not self._lookahead:
            raise EOFError("Unexpected end of file")

        token = self._lookahead
        self._lookahead = self._lexer.get_next_token()
        return token


if __name__ == "__main__":
    with open("sample.txt.bak") as file:
        target = file.read()

    parser = Parser(Lexer(token_spec))
    ast = parser.parse(target)
    with open("res.json", "w") as file:
        file.write(json.dumps(ast))
