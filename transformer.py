import json
import subprocess
from typing import Dict


class PySparkTransformer:
    def transform(self, ast: Dict):
        res = []
        for item in ast["body"]:
            if item['type'] == 'VariableAssignment':
                res.append(self.create_variable_assignment(item))
            if item["type"] == "ProjectExpression":
                res.append(self.create_project_expression(item))
        return "\n".join(res)

    def create_variable_assignment(self, item: Dict) -> str:
        if item["value"]["type"] == "BlockStatement":
            body = self.create_block_statement(item["value"])

        elif item["value"]["type"] == "ProjectExpression":
            body = self.create_project_expression(item["value"])
        else:
            body = self.create_expression(item["value"])

        return f"{item['name']} = (\n{body}\n.alias('{item['name']}')\n)\n"

    def create_block_statement(self, stmt: Dict):
        col_assignments = stmt["body"][0]['body']
        assignments = []
        source_table = self.get_source_table(col_assignments[0])
        for col_assignment in col_assignments:
            assignments.append(
                f"{self.create_expression(col_assignment['value'])}.alias('{col_assignment['name']['value']}')"
            )
        filters = stmt["body"][1]["body"] if len(stmt["body"]) > 1 else []
        filter_stmts = [self.create_filter(_filter) for _filter in filters]
        joined_assignments = ',\n'.join(assignments)
        joined_filters = '\n.'.join(filter_stmts)
        res = f"{source_table}.select(\n{joined_assignments}\n)"
        if joined_filters:
            res = f"{res}\n.{joined_filters}"

        if stmt.get('modifier'):
            res = f"{res}.\n{stmt['modifier']}()"
        return res

    def create_project_expression(self, expr: Dict) -> str:
        return self.create_block_statement(expr['body'])


    def get_source_table(self, expr) -> str:
        if "source_table" in expr:
            return expr["source_table"]

        for value in expr.values():
            if isinstance(value, dict):
                res = self.get_source_table(value)
                if res:
                    return res

            if isinstance(value, list):
                for data in value:
                    res = self.get_source_table(data)
                    if res:
                        return res

    def create_filter(self, expr: Dict) -> str:
        if expr["value"] == "where":
            return f"filter({self.create_expression(expr['body'])})"

        if expr['value'] == "having":
            return f"agg({self.create_expression(expr['body'])})"

        if expr["value"] == "group by":
            return f"groupBy({self.create_column_assignment_list(expr['body'])})"

    def create_join(self, join: Dict) -> str:
        if join["left"]["type"] == "JoinExpression":
            left = self.create_join(join["left"])
            combined = f"""{left}.join({join['right']['value']}, on={self.create_expression(join["condition"])}, how="{join["join_type"]}")"""
            return combined
        if join["left"]["type"] == "UnionExpression":
            left = self.create_union_expression(join["left"])
            combined = f"""{left}.join({join['right']['value']}, on={self.create_expression(join["condition"])}, how="{join["join_type"]}")"""
            return combined
        return f"""{join["left"]["value"]}.join({join["right"]["value"]}, on={self.create_expression(join["condition"])}, how="{join["join_type"]}")"""

    def create_column_assignment_list(self, expr: Dict) -> str:
        return ",".join([self.create_expression(item) for item in expr["body"]])

    def create_expression(self, expr: Dict) -> str:
        if expr["type"] == "MembershipExpression":
            return self.create_membership_expression(expr)

        if expr["type"] == "BinaryExpression":
            return self.create_binary_expression(expr)
        if expr["type"] == "ParenthesizedExpression":
            return self.create_parenthesized_expression(expr)

        if expr["type"] == "FunctionalExpression":
            return self.create_functional_expression(expr)

        if expr["type"] == "IdentifierExpression":
            return self.create_identifier_expression(expr)

        if expr['type'] == "ArrayExpression":
            return self.create_array_expression(expr)

        if expr["type"] == "MatchExpression":
            return self.create_match_expression(expr)

        if expr["type"] == "CaseExpression":
            return self.create_case_expression(expr)

        if expr["type"] == "UnionExpression":
            return self.create_union_expression(expr)

        if expr["type"] == "JoinExpression":
            return self.create_join(expr)

        return self.create_literal(expr)

    def create_union_expression(self, expr: Dict) -> str:
        left = self.create_expression(expr["left"])
        right = self.create_expression(expr["right"])
        return f"\n{left}.union({right})\n"

    def create_match_expression(self, expr: Dict) -> str:
        cases = []
        for case in expr["body"]:
            cases.append(self.create_expression(case))
        joined_cases = "\n.".join(cases)
        return joined_cases

    def create_case_expression(self, expr: Dict) -> str:
        if expr["conditions"]["type"] == "IdentifierExpression" and expr["conditions"]["value"] == "_":
            return f"otherwise({self.create_expression(expr['value'])})"
        return f"when(\n{self.create_expression(expr['conditions'])}, {self.create_expression(expr['value'])}\n)"

    def create_literal(self, expr: Dict) -> str:
        if expr["type"] == "StringLiteral":
            return f'"{expr["value"]}"'
        if expr['type'] == "NumericLiteral":
            return expr['value']

        if expr["type"] == "BooleanLiteral":
            return expr['value']

    def create_membership_expression(self, expr: Dict) -> str:
        return f"{self.create_expression(expr['left'])}.isin({self.create_expression(expr['right'])})"

    def create_array_expression(self, expr: Dict) -> str:
        return str([f'{item["value"]}' for item in expr["body"]])

    def create_identifier_expression(self, expr):
        val = expr['value'].split(".")
        if len(val) == 1:
            return expr['value']
        return f"{val[0]}['{'.'.join(val[1:])}']"

    def create_functional_expression(self, expr: Dict) -> str:
        return f"{expr['name']}({','.join(self.create_expression(arg) for arg in expr['args'])})"

    def create_parenthesized_expression(self, expr):
        return f'({self.create_expression(expr["body"])})'

    def create_binary_expression(self, expr):
        left = self.create_expression(expr["left"])
        right = self.create_expression(expr["right"])
        left_paren = ""
        right_paren = ""

        if expr["operator"] == "!=" and not right:
            return f"{left_paren}{left}{right_paren}.isNotNull()"

        if expr["operator"] in ("and", "or"):
            left_paren = "("
            right_paren = ")"

        return f"{left_paren}{left}{right_paren} {self.create_operator(expr['operator'])} {left_paren}{right}{right_paren}"

    def create_operator(self, operator: str) -> str:
        if operator == "and":
            return "&"
        if operator == "or":
            return "|"
        return operator


if __name__ == "__main__":
    trans = PySparkTransformer()
    with open("res.json") as file:
        sample = json.load(file)
    res = trans.transform(sample)
    with open("pyspark.py", "w") as file:
        file.write(res)

    subprocess.run(["black",  "pyspark.py", "--skip-magic-trailing-comma"])
