import ast
import operator
from datetime import datetime

import os
from exa_py import Exa
from langchain_core.tools import tool


@tool
def exa_search(query: str) -> str:
    """Ищет актуальную информацию в интернете через сервис EXA.
    Используй этот инструмент, когда на текущей странице нет ответа
    или нужны свежие данные. На вход — поисковый запрос."""
    try:
        exa = Exa(api_key=os.environ["EXA_API_KEY"])
        response = exa.search_and_contents(query, num_results=5, text=True)
    except Exception as exc:  # noqa: BLE001
        # Сетевой/Cloudflare-блок или сбой EXA не должен ронять весь ответ —
        # возвращаем короткое сообщение (без HTML тела ошибки), агент ответит по странице.
        return (
            f"Веб-поиск через EXA сейчас недоступен ({type(exc).__name__}). "
            "Ответь по содержимому страницы, если возможно."
        )
    blocks = []
    for r in response.results:
        text = (r.text or "")[:600]
        blocks.append(f"### {r.title}\nURL: {r.url}\n{text}")
    if not blocks:
        return "По запросу ничего не найдено."
    return "\n\n".join(blocks)


def _pow_guarded(a, b):
    if abs(b) > 1000:
        raise ValueError("слишком большая степень")
    return operator.pow(a, b)


_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: _pow_guarded,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _eval_node(node):
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.operand))
    raise ValueError("недопустимый элемент выражения")


@tool
def calculator(expression: str) -> str:
    """Вычисляет арифметическое выражение: числа, скобки и операции
    + - * / // % **. Используй для любых точных расчётов вместо счёта в уме."""
    try:
        result = _eval_node(ast.parse(expression, mode="eval"))
    except ZeroDivisionError:
        return "Ошибка: деление на ноль."
    except Exception:  # noqa: BLE001
        return (
            "Не удалось вычислить. Допустимы только числа, скобки и операции "
            "+ - * / // % ** (степень не больше 1000)."
        )
    return f"{expression} = {result}"


_WEEKDAYS = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]


@tool
def current_datetime() -> str:
    """Возвращает текущие дату, время и день недели. Используй, когда вопрос
    касается «сегодня», «сейчас», текущего года — не угадывай их."""
    now = datetime.now().astimezone()
    return f"Сейчас {now.isoformat(timespec='seconds')}, {_WEEKDAYS[now.weekday()]}."
