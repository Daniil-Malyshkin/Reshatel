# -*- coding: utf-8 -*-
"""Решатель — пошаговый решатель уравнений, неравенств и систем."""

import re
import sympy as sp
from sympy.parsing.sympy_parser import (
    parse_expr, standard_transformations,
    implicit_multiplication_application, convert_xor
)

VERSION = '1.0'

# Переменные создаются для всех латинских букв; регистр различается.
VARIABLES = {name: sp.Symbol(name, real=True) for name in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'}
x, y = VARIABLES['x'], VARIABLES['y']
TRANSFORMATIONS = standard_transformations + (
    implicit_multiplication_application,
    convert_xor,
)

SAFE = {
    **VARIABLES,
    'sqrt': sp.sqrt,
    'root': lambda n, value: sp.real_root(value, n),
    'sin': sp.sin, 'cos': sp.cos, 'tan': sp.tan,
    'Abs': sp.Abs, 'abs': sp.Abs,
    'pi': sp.pi, 'log': sp.log, 'exp': sp.exp,
}

# parse_expr uses eval internally; never expose Python builtins to user input.
SAFE_GLOBALS = {
    '__builtins__': {},
    'Symbol': sp.Symbol, 'Integer': sp.Integer, 'Float': sp.Float,
    'Rational': sp.Rational, 'Add': sp.Add, 'Mul': sp.Mul, 'Pow': sp.Pow,
}

def pretty(value):
    return sp.pretty(sp.sympify(value), use_unicode=True)

def compact(value):
    text = sp.sstr(sp.sympify(value))
    text = text.replace('**2', '²').replace('**3', '³')
    text = text.replace('sqrt(', '√(').replace('**', '^')
    text = text.replace('atan', 'arctan').replace('asin', 'arcsin').replace('acos', 'arccos')
    text = text.replace('log(', 'log(').replace('*', '·').replace('pi', 'π')
    text = re.sub(r'√\(([-+]?\w+)\)', r'√\1', text)
    text = text.replace('ℯ', 'e')
    text = re.sub(r'\bE\b', 'e', text)
    text = re.sub(r'\bI\b', 'i', text)
    text = re.sub(r'\bzoo\b', 'не определено', text)
    return text

def eq_text(left, right):
    return f'{compact(left)} = {compact(right)}'

def make_step(text, explanation):
    return (text, explanation)

def equation_answer(solution, var):
    if solution == sp.EmptySet:
        return 'действительных решений нет'
    if solution == sp.S.Reals:
        return 'любое действительное число'
    if isinstance(solution, sp.FiniteSet):
        values = sorted(solution.args, key=sp.default_sort_key)
        if len(values) == 1:
            return f'{var} = {compact(values[0])}'
        labels = ['₁', '₂', '₃', '₄', '₅', '₆']
        return '; '.join(
            f'{var}{labels[i - 1] if i <= len(labels) else i} = {compact(value)}'
            for i, value in enumerate(values, 1)
        )
    return set_text(solution)

def _replace_braced_command(source, command, replacement):
    """Преобразует простую TeX-команду с одним или двумя аргументами."""
    pattern = re.compile(r'\\' + command + r'\s*\{')
    while True:
        match = pattern.search(source)
        if not match:
            return source
        def read_group(pos):
            if pos >= len(source) or source[pos] != '{':
                return None, pos
            depth, i = 1, pos + 1
            while i < len(source) and depth:
                if source[i] == '{':
                    depth += 1
                elif source[i] == '}':
                    depth -= 1
                i += 1
            return (source[pos + 1:i - 1], i) if depth == 0 else (None, pos)
        first, end = read_group(match.end() - 1)
        if first is None:
            return source
        args = [first]
        if command == 'frac':
            while end < len(source) and source[end].isspace():
                end += 1
            second, end2 = read_group(end)
            if second is None:
                return source
            args.append(second)
            end = end2
        rendered = replacement(*args)
        source = source[:match.start()] + rendered + source[end:]


def normalize_math_input(text):
    """Принимает обычный текст, Unicode и распространённую вставку из LaTeX/Word."""
    s = str(text).strip()
    # Частые команды LaTeX, которые попадают в буфер обмена из редакторов формул.
    s = s.replace(r'\(', '').replace(r'\)', '').replace(r'\[', '').replace(r'\]', '')
    s = s.replace(r'\left', '').replace(r'\right', '')
    s = s.replace(r'\cdot', '*').replace(r'\times', '*').replace(r'\div', '/')
    s = s.replace(r'\pi', 'pi').replace(r'\sin', 'sin').replace(r'\cos', 'cos')
    s = s.replace(r'\tan', 'tan').replace(r'\tg', 'tg').replace(r'\log', 'log')
    s = s.replace(r'\ln', 'ln').replace(r'\sqrt', 'sqrt')
    s = s.replace(r'\dfrac', r'\frac').replace(r'\tfrac', r'\frac')
    s = _replace_braced_command(s, 'frac', lambda a, b: f'(({a})/({b}))')
    s = _replace_braced_command(s, 'sqrt', lambda a: f'sqrt({a})')
    # Преобразуем простые фигурные группы в круглые скобки после обработки команд.
    s = s.replace('{', '(').replace('}', ')')
    s = s.replace('≤', '<=').replace('≥', '>=').replace('≠', '!=')
    s = s.replace('＝', '=').replace('﹣', '-').replace('＋', '+')
    s = s.replace('√', 'sqrt')
    s = re.sub(r'(?i)\bsqrt(\d+(?:\.\d+)?|[A-Za-z])\b', r'sqrt(\1)', s)
    s = s.replace('⁄', '/').replace('−', '-').replace('–', '-').replace('—', '-')
    s = s.replace('×', '*').replace('·', '*').replace('∙', '*').replace('÷', '/')
    s = s.replace('π', 'pi')
    # Убираем пробелы между названием функции и открывающей скобкой.
    s = re.sub(r'(?i)\b(sqrt|sin|cos|tan|tg|ctg|log|ln|lg)\s*\(', r'\1(', s)
    return s


def parse_math(text):
    s = normalize_math_input(text)
    if not s:
        raise ValueError('Не хватает выражения — проверьте ввод.')
    forbidden = ('"', "'", '[', ']', ':', '@', '#', '$', '%', '&', '\\')
    if len(s) > 220 or '__' in s or any(ch in s for ch in forbidden):
        raise ValueError('Ввод содержит недопустимые символы или слишком длинный текст. Используйте математическую запись.')
    if not re.fullmatch(r'[A-Za-zА-Яа-яЁё0-9_+\-*/^=<>!().,;|\sπ·×÷∙–—−²³⁴⁵⁶⁷⁸⁹]+', s):
        raise ValueError('Используйте только числа, переменные, математические знаки и названия функций.')
    s = s.replace('−', '-').replace('–', '-').replace('—', '-')
    s = s.replace('×', '*').replace('·', '*').replace('∙', '*').replace('÷', '/')
    s = s.replace('π', 'pi')
    # ASCIIMath иногда записывает корень n-й степени как root(n)(выражение).
    root_pattern = re.compile(r'\broot\s*\(\s*(\d+)\s*\)\s*\(', re.IGNORECASE)
    while True:
        match = root_pattern.search(s)
        if not match:
            break
        depth = 1
        end = match.end()
        while end < len(s) and depth:
            if s[end] == '(':
                depth += 1
            elif s[end] == ')':
                depth -= 1
            end += 1
        if depth:
            break
        argument = s[match.end():end - 1]
        s = s[:match.start()] + f'root({match.group(1)}, {argument})' + s[end:]
    # Нормализуем верхние индексы до проверки имён функций: sin²(x) -> sin^2(x).
    for superscript, power in {'⁰':'0','¹':'1','²':'2','³':'3','⁴':'4','⁵':'5','⁶':'6','⁷':'7','⁸':'8','⁹':'9'}.items():
        s = s.replace(superscript, '^' + power)
    allowed_calls = {'sqrt', 'root', 'sin', 'cos', 'tan', 'tg', 'ctg', 'abs', 'log', 'lg', 'ln', 'exp'}
    for call_name in re.findall(r'(?i)(?<![A-Za-z_])([A-Za-z_]\w*)\s*\(', s):
        normalized_call = call_name.lower()
        is_log_base = bool(re.fullmatch(r'log_?\d+', normalized_call))
        if normalized_call not in allowed_calls and not is_log_base:
            raise ValueError(f'Функция «{call_name}» не поддерживается. Используйте математические функции из списка.')
    s = re.sub(r'(?<=\d),(?=\d)', '.', s)
    protected = {}
    counter = 0
    def protect(match):
        nonlocal counter
        counter += 1
        token = f'__TRIG{counter}__'
        protected[token] = f'{match.group(1)}({match.group(3)})^{match.group(2)}'
        return token
    s = re.sub(r'(?i)(?<![A-Za-z_])(sin|cos|tan)\s*\^\s*(\d+)\s*\(?\s*([A-Za-z]\w*)\s*\)?', lambda m: protect(m), s)
    s = re.sub(r'(?i)(?<![A-Za-z_])(sin|cos|tan)\s*(\d+)\s*([A-Za-z]\w*)', r'\1(\2\3)', s)
    s = re.sub(r'(?i)(?<![A-Za-z_])ctg\s*\(\s*([^(),]*)\s*\)', r'(1/tan(\1))', s)
    s = re.sub(r'(?i)(?<![A-Za-z_])ctg\s*([A-Za-z]\w*)', r'(1/tan(\1))', s)
    s = re.sub(r'(?i)(?<![A-Za-z_])tg\s*\(\s*([^(),]*)\s*\)', r'tan(\1)', s)
    s = re.sub(r'(?i)(?<![A-Za-z_])tg\s*([A-Za-z]\w*)', r'tan(\1)', s)
    for name in ('sin', 'cos', 'tan'):
        s = re.sub(rf'(?i)(?<![A-Za-z_]){name}\s*\(\s*([A-Za-z]\w*)\s*\)', rf'{name}(\1)', s)
        s = re.sub(rf'(?i)(?<![A-Za-z_]){name}\s+([A-Za-z]\w*)', rf'{name}(\1)', s)
        s = re.sub(rf'(?i)(?<![A-Za-z_]){name}([A-Za-z]\w*)', rf'{name}(\1)', s)
    s = re.sub(r'(?i)\blog_\s*(\d+)\s*\(([^(),]*)\)', r'log(\2,\1)', s)
    s = re.sub(r'(?i)\blog(\d+)\s*\(([^(),]*)\)', r'log(\2,\1)', s)
    s = re.sub(r'(?i)\blg\s*\(([^(),]*)\)', r'log(\1,10)', s)
    s = re.sub(r'(?i)\bln\s*\(([^(),]*)\)', r'log(\1)', s)
    s = re.sub(r'\|([^|]+)\|', r'Abs(\1)', s)
    for token, value in protected.items():
        s = s.replace(token, value)
    s = re.sub(r'(?<=\d)(?=[A-Za-z])', '*', s)
    expr = parse_expr(s, local_dict=SAFE, global_dict=SAFE_GLOBALS, transformations=TRANSFORMATIONS, evaluate=True)
    floats = expr.atoms(sp.Float)
    if floats:
        expr = expr.xreplace({f: sp.Rational(str(f)) for f in floats})
    return expr

def relation_parts(text):
    for op in ('<=', '>=', '!=', '<', '>', '='):
        if op in text:
            left, right = text.split(op, 1)
            return op, parse_math(left), parse_math(right)
    return None, parse_math(text), sp.Integer(0)

def linear_equation_steps(left, right, var):
    expr = sp.expand(left - right)
    poly = sp.Poly(expr, var) if expr.is_polynomial(var) else None
    if not poly or poly.degree() != 1:
        return None
    a, b_norm = poly.all_coeffs()
    solution = sp.solveset(sp.Eq(left, right), var, domain=sp.S.Reals)
    answer_text = equation_answer(solution, var)
    steps = [make_step(f'Исходное уравнение: {eq_text(left, right)}', f'Записываем исходное уравнение. Наша задача — оставить {var} отдельно и найти его значение.')]
    if not right.free_symbols and not (left.free_symbols - {var}):
        left_poly = sp.Poly(sp.expand(left), var)
        a = left_poly.coeff_monomial(var)
        b = left_poly.coeff_monomial(1)
        c = sp.simplify(right)
        new_right = sp.simplify(c - b)
        if b != 0:
            steps.append(make_step(f'{compact(a)}·{var} = {compact(c)} − ({compact(b)})', f'Убираем свободное число {compact(b)}. Для этого переносим его в правую часть с противоположным знаком.'))
            steps.append(make_step(f'{compact(a)}·{var} = {compact(new_right)}', f'Считаем: {compact(c)} − ({compact(b)}) = {compact(new_right)}. Теперь рядом с {var} осталось только число {compact(a)}.'))
        else:
            steps.append(make_step(f'{compact(a)}·{var} = {compact(c)}', f'Свободного слагаемого нет, поэтому сразу получаем {compact(a)}·{var} = {compact(c)}.'))
        root = sp.simplify(new_right / a)
        steps.append(make_step(f'{var} = {compact(new_right)} / {compact(a)}', f'Делим обе части на {compact(a)}, чтобы оставить только {var}.'))
        steps.append(make_step(f'{var} = {compact(root)}', f'Выполняем деление: {compact(new_right)} / {compact(a)} = {compact(root)}.'))
        steps.append(make_step(f'Ответ: {answer_text}', 'Полученное значение подходит исходному уравнению, поэтому это итоговый ответ.'))
        return steps, answer_text
    root = sp.simplify(-b_norm / a)
    coeff = '' if a == 1 else f'{compact(a)}·'
    steps.append(make_step(f'{coeff}{var} = {compact(-b_norm)}', 'Переносим все слагаемые без неизвестной в правую часть, а слагаемые с неизвестной оставляем слева.'))
    steps.append(make_step(f'{var} = ({compact(-b_norm)}) / {compact(a)}', f'Делим обе части на {compact(a)}, чтобы оставить только {var}.'))
    steps.append(make_step(f'{var} = {compact(root)}', f'Вычисляем: {compact(-b_norm)} / {compact(a)} = {compact(root)}.'))
    steps.append(make_step(f'Ответ: {answer_text}', 'Полученное значение является решением исходного уравнения.'))
    return steps, answer_text

def quadratic_equation_steps(left, right, var):
    expr = sp.expand(left - right)
    poly = sp.Poly(expr, var)
    a, b, c = poly.all_coeffs()
    solution = sp.solveset(sp.Eq(left, right), var, domain=sp.S.Reals)
    answer_text = equation_answer(solution, var)
    steps = [make_step(f'Исходное уравнение: {eq_text(left, right)}', f'Квадратное уравнение приводим к стандартному виду a·{var}² + b·{var} + c = 0.')]
    steps.append(make_step(f'a = {compact(a)}, b = {compact(b)}, c = {compact(c)}', f'Определяем коэффициенты квадратного уравнения: a = {compact(a)}, b = {compact(b)}, c = {compact(c)}.'))
    steps.append(make_step('D = b² − 4ac', 'Сначала находим дискриминант. Он помогает определить количество действительных корней и используется дальше в формуле корней.'))
    D = sp.simplify(b ** 2 - 4 * a * c)
    D_first = sp.simplify(b ** 2)
    D_second = sp.simplify(4 * a * c)
    steps.append(make_step(f'D = ({compact(b)})² − 4·{compact(a)}·{compact(c)}', 'Подставляем конкретные значения a, b и c в формулу дискриминанта.'))
    steps.append(make_step(f'D = {compact(D_first)} − {compact(D_second)} = {compact(D)}', f'Сначала считаем квадрат и произведение: {compact(D_first)} − {compact(D_second)} = {compact(D)}.'))
    if D.is_negative:
        steps.append(make_step('D < 0', 'Дискриминант отрицательный, поэтому квадратное уравнение не имеет действительных корней.'))
        steps.append(make_step(f'Ответ: {answer_text}', 'Множество действительных решений пустое.'))
        return steps, answer_text
    if D.is_zero:
        steps.append(make_step(f'{var} = −b / (2a)', 'При D = 0 оба корня совпадают, поэтому используем формулу одного корня.'))
        root = sp.simplify(-b / (2 * a))
        steps.append(make_step(f'{var} = −({compact(b)}) / (2·{compact(a)})', 'Подставляем числовые значения b и a в формулу.'))
        steps.append(make_step(f'{var} = {compact(-b)} / {compact(2 * a)} = {compact(root)}', f'Выполняем вычисления: {compact(-b)} / {compact(2 * a)} = {compact(root)}.'))
        steps.append(make_step(f'Ответ: {answer_text}', 'Это единственный действительный корень.'))
        return steps, answer_text
    steps.append(make_step(f'{var}₁,₂ = (−b ± √D) / (2a)', 'Используем формулу корней квадратного уравнения.'))
    r1 = sp.simplify((-b + sp.sqrt(D)) / (2 * a))
    r2 = sp.simplify((-b - sp.sqrt(D)) / (2 * a))
    num1 = sp.simplify(-b + sp.sqrt(D))
    den = sp.simplify(2 * a)
    num2 = sp.simplify(-b - sp.sqrt(D))
    steps.append(make_step(f'{var}₁ = (−({compact(b)}) + √{compact(D)}) / (2·{compact(a)})', 'Для первого корня выбираем знак «+» и подставляем a, b и D.'))
    steps.append(make_step(f'{var}₁ = ({compact(-b)} + {compact(sp.sqrt(D))}) / {compact(den)} = {compact(num1)} / {compact(den)}', 'Сначала считаем −b и корень из дискриминанта, затем складываем числитель.'))
    steps.append(make_step(f'{var}₁ = {compact(r1)}', f'Делим {compact(num1)} на {compact(den)} и получаем первый корень.'))
    steps.append(make_step(f'{var}₂ = (−({compact(b)}) − √{compact(D)}) / (2·{compact(a)})', 'Для второго корня выбираем знак «−» и снова подставляем числа.'))
    steps.append(make_step(f'{var}₂ = ({compact(-b)} − {compact(sp.sqrt(D))}) / {compact(den)} = {compact(num2)} / {compact(den)}', 'Считаем числитель второго корня: −b − √D.'))
    steps.append(make_step(f'{var}₂ = {compact(r2)}', f'Делим {compact(num2)} на {compact(den)} и получаем второй корень.'))
    steps.append(make_step(f'Ответ: {answer_text}', 'Оба найденных значения удовлетворяют исходному квадратному уравнению.'))
    return steps, answer_text

# --- восстановленная и дополненная часть -----------------------------------

def base_text(base):
    if base == sp.E:
        return 'e'
    return compact(base)

def direct_log_equation_steps(text, var=None):
    cleaned = text.strip().replace('−', '-')
    patterns = [
        (r'^log_([0-9]+)\s*\(([^(),]*)\)\s*=\s*(.+)$', 'base'),
        (r'^log(\d+)\s*\(([^(),]*)\)\s*=\s*(.+)$', 'base'),
        (r'^log₂\s*\(([^(),]*)\)\s*=\s*(.+)$', 'base2'),
        (r'^log\s*\(([^(),]*)\)\s*=\s*(.+)$', 'ten'),
        (r'^lg\s*\(([^(),]*)\)\s*=\s*(.+)$', 'ten'),
        (r'^ln\s*\(([^(),]*)\)\s*=\s*(.+)$', 'natural'),
    ]
    for pattern, kind in patterns:
        match = re.match(pattern, cleaned)
        if not match:
            continue
        if kind == 'base':
            base = sp.Integer(int(match.group(1)))
            arg_text, rhs_text = match.group(2), match.group(3)
        elif kind == 'base2':
            base = sp.Integer(2)
            arg_text, rhs_text = match.group(1), match.group(2)
        elif kind == 'ten':
            base = sp.Integer(10)
            arg_text, rhs_text = match.group(1), match.group(2)
        else:
            base = sp.E
            arg_text, rhs_text = match.group(1), match.group(2)

        arg = parse_math(arg_text)
        rhs = parse_math(rhs_text)
        if var is None:
            candidates = (arg.free_symbols | rhs.free_symbols)
            var = next(iter(candidates), x)
        steps = [
            make_step(
                f'Исходное уравнение: log_{base_text(base)}({compact(arg)}) = {compact(rhs)}',
                'Логарифмическое уравнение решаем переходом к показательному виду.',
            ),
            make_step(
                f'ОДЗ: {compact(arg)} > 0',
                'Аргумент логарифма должен быть строго больше нуля.',
            ),
        ]
        if rhs.free_symbols:
            return None
        powered = sp.simplify(base ** rhs)
        steps.append(make_step(
            f'{compact(arg)} = {base_text(base)}^{compact(rhs)} = {compact(powered)}',
            'По определению логарифма: log_b(a) = c означает a = b^c.',
        ))
        solution = sp.solveset(sp.Eq(arg, powered), var, domain=sp.S.Reals)
        answer_text = equation_answer(solution, var)
        steps.append(make_step(
            f'{compact(arg)} = {compact(powered)}',
            'Получили уравнение без логарифмов и решили его.',
        ))
        steps.append(make_step(
            f'Ответ: {answer_text}',
            'Проверяем, что найденное значение входит в ОДЗ.',
        ))
        return steps, answer_text
    return None

def _compact_plain(value):
    return re.sub(r'\boo\b', '∞', compact(value))

def set_text(value, var=None):
    """Читаемое представление множества решений, включая общие тригонометрические решения."""
    if value == sp.EmptySet:
        return 'решений нет'
    if value == sp.S.Reals:
        return 'любое действительное число'
    if isinstance(value, sp.FiniteSet):
        values = sorted(value.args, key=sp.default_sort_key)
        if not values:
            return 'решений нет'
        return '; '.join(_compact_plain(v) for v in values)
    if isinstance(value, sp.ImageSet):
        parameters = value.lamda.variables
        expression = value.lamda.expr
        if len(parameters) == 1 and value.base_set == sp.S.Integers:
            parameter = parameters[0]
            base = sp.simplify(expression.subs(parameter, 0))
            period = sp.simplify(sp.diff(expression, parameter))
            name = str(var) if var is not None else 'x'
            period_text = _compact_plain(period)
            if period == sp.pi:
                period_text = 'π'
            elif period == -sp.pi:
                period_text = '−π'
            if base == 0:
                return f'{name} = {period_text}k, k ∈ ℤ'
            return f'{name} = {_compact_plain(base)} + {period_text}k, k ∈ ℤ'
        return _compact_plain(value)
    if isinstance(value, sp.Interval):
        left = '(' if value.left_open else '['
        right = ')' if value.right_open else ']'
        return f'{left}{_compact_plain(value.start)}; {_compact_plain(value.end)}{right}'
    if isinstance(value, sp.Union):
        separator = ' или ' if all(isinstance(arg, sp.ImageSet) for arg in value.args) else ' ∪ '
        return separator.join(set_text(arg, var) for arg in value.args)
    if isinstance(value, sp.Complement):
        return f'{set_text(value.args[0], var)} без {set_text(value.args[1], var)}'
    return _compact_plain(value)

def _single_var(left, right):
    symbols = (left.free_symbols | right.free_symbols)
    if len(symbols) == 1:
        return next(iter(symbols))
    return None

def inequality_steps(op, left, right, var):
    rel_map = {'<': sp.Lt, '<=': sp.Le, '>': sp.Gt, '>=': sp.Ge, '!=': sp.Ne}
    relation = rel_map[op](left, right)
    try:
        solution = sp.solveset(relation, var, domain=sp.S.Reals)
    except Exception:
        solution = sp.EmptySet
    answer_text = set_text(solution)
    steps = [
        make_step(
            f'Исходное неравенство: {compact(left)} {op} {compact(right)}',
            'Решаем неравенство относительно переменной.',
        ),
        make_step(
            f'{compact(left - right)} {op} 0',
            'Переносим все слагаемые в левую часть, чтобы сравнивать с нулём.',
        ),
        make_step(
            f'Ответ: {answer_text}',
            'Записываем множество значений переменной, при которых неравенство выполняется.',
        ),
    ]
    return steps, answer_text

def generic_equation_steps(left, right, var):
    eq = sp.Eq(left, right)
    expr = sp.simplify(left - right)
    steps = [
        make_step(
            f'Исходное уравнение: {eq_text(left, right)}',
            f'Приводим уравнение к виду f({var}) = 0 и ищем действительные корни.',
        ),
        make_step(
            f'{compact(expr)} = 0',
            'Переносим всё в левую часть и упрощаем.',
        ),
    ]
    factored = sp.factor(expr)
    if factored != expr:
        steps.append(make_step(
            f'{compact(factored)} = 0',
            'Раскладываем левую часть на множители.',
        ))
        steps.append(make_step(
            'Произведение равно нулю, когда хотя бы один множитель равен нулю.',
            'Приравниваем каждый множитель к нулю и решаем получившиеся уравнения.',
        ))
    solution = sp.solveset(eq, var, domain=sp.S.Reals)
    if expr.has(sp.sin, sp.cos, sp.tan):
        answer_text = set_text(solution, var)
        note = ('Для тригонометрического уравнения записаны общие решения. '
                'k — любое целое число, поэтому учитываются все периоды функции.')
    else:
        simple = None
        try:
            simple = sp.solve(eq, var)
        except Exception:
            simple = None
        if simple:
            answer_text = '; '.join(f'{var} = {_compact_plain(v)}' for v in simple)
            note = 'Найденные значения — действительные корни уравнения.'
        else:
            answer_text = set_text(solution, var)
            if answer_text == 'решений нет':
                note = 'С учётом ОДЗ уравнение не имеет действительных решений.'
            else:
                note = 'Записываем множество действительных решений.'
    steps.append(make_step(f'Ответ: {answer_text}', note))
    return steps, answer_text

def system_steps(text):
    parts = [p.strip() for p in re.split(r'[;\n]', text) if p.strip()]
    if len(parts) < 2:
        return None
    equations = []
    for part in parts:
        op, left, right = relation_parts(part)
        if op != '=':
            return None
        equations.append(sp.Eq(left, right))
    variables = sorted(
        {s for e in equations for s in e.free_symbols},
        key=sp.default_sort_key,
    )
    if not variables:
        return None
    steps = [make_step(
        'Система уравнений:\n' + '\n'.join(
            f'{pretty(e.lhs)} = {pretty(e.rhs)}' for e in equations
        ),
        'Решаем уравнения системы совместно.',
    )]
    try:
        solutions = sp.solve(equations, variables, dict=True)
    except Exception:
        solutions = []
    if not solutions:
        answer_text = 'решений нет'
    else:
        answer_text = '; '.join(
            ', '.join(f'{var} = {_compact_plain(value)}' for var, value in solution.items())
            for solution in solutions
        )
    steps.append(make_step(
        f'Ответ: {answer_text}',
        'Найденные значения удовлетворяют всем уравнениям системы.',
    ))
    return steps, answer_text

def interval_from_chain(condition, var):
    """Разбирает запись вида 0 <= x < 2*pi и возвращает интервал."""
    parts = re.split(r'(<=|>=|<|>)', condition)
    if len(parts) != 5:
        raise ValueError('Условие промежутка запишите, например: 0 <= x < 2*pi.')
    left_text, op1, middle_text, op2, right_text = [part.strip() for part in parts]
    middle = parse_math(middle_text)
    if middle != var:
        raise ValueError('В условии промежутка между знаками сравнения должна стоять та же переменная, что и в уравнении.')
    left_bound = parse_math(left_text)
    right_bound = parse_math(right_text)
    if left_bound.free_symbols or right_bound.free_symbols:
        raise ValueError('Границы промежутка должны быть числами или выражениями без переменных.')
    if op1 == '<=':
        lower, lower_open = left_bound, False
    elif op1 == '<':
        lower, lower_open = left_bound, True
    elif op1 == '>=':
        upper, upper_open = left_bound, False
    else:
        upper, upper_open = left_bound, True
    if op2 == '<=':
        upper, upper_open = right_bound, False
    elif op2 == '<':
        upper, upper_open = right_bound, True
    elif op2 == '>=':
        lower, lower_open = right_bound, False
    else:
        lower, lower_open = right_bound, True
    if 'lower' not in locals() or 'upper' not in locals():
        raise ValueError('Не удалось определить обе границы промежутка. Используйте запись: a <= x < b.')
    return sp.Interval(lower, upper, left_open=lower_open, right_open=upper_open)


def equation_with_interval_steps(equation, condition):
    op, left, right = relation_parts(equation)
    if op != '=':
        raise ValueError('В первой строке должно быть уравнение, а во второй — условие промежутка.')
    var = _single_var(left, right)
    if var is None:
        raise ValueError('Не удалось определить переменную уравнения.')
    interval = interval_from_chain(condition, var)
    solution_all = sp.solveset(sp.Eq(left, right), var, domain=sp.S.Reals)
    solution = sp.Intersection(solution_all, interval)
    answer = set_text(solution, var)
    steps = [
        make_step(f'Уравнение: {eq_text(left, right)}', 'Сначала находим все действительные решения уравнения.'),
        make_step(f'Ограничение: {condition}', f'Учитываем, что {var} принадлежит промежутку {set_text(interval)}.'),
        make_step(f'Все решения: {set_text(solution_all, var)}', 'Записываем общее решение уравнения.'),
        make_step(f'Пересечение с промежутком: {answer}', 'Оставляем только те корни, которые входят в заданный промежуток.'),
        make_step(f'Ответ: {answer}', 'Это решения уравнения с учётом указанного ограничения.'),
    ]
    return steps, answer


def solve_problem(text):
    text = normalize_math_input(text).strip()
    if not text:
        raise ValueError('Введите задачу.')

    # Многострочная запись «уравнение + ограничение промежутка».
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) == 2 and re.search(r'(<=|>=|<|>)', lines[1]):
        return equation_with_interval_steps(lines[0], lines[1])
    if len(lines) > 1:
        raise ValueError('Не удалось разобрать несколько строк. Для промежутка укажите уравнение в первой строке, а условие вида 0 <= x < 2*pi — во второй.')

    system = system_steps(text)
    if system:
        return system

    log_solution = direct_log_equation_steps(text)
    if log_solution:
        return log_solution

    op, left, right = relation_parts(text)

    if op is None:
        value = sp.simplify(left)
        steps = [
            make_step(f'Выражение: {text}', 'Упрощаем заданное выражение.'),
            make_step(
                f'Результат: {compact(value)}',
                'Приводим подобные слагаемые и выполняем возможные преобразования.',
            ),
        ]
        return steps, compact(value)

    var = _single_var(left, right)

    if var is None:
        if op == '=':
            symbols = left.free_symbols | right.free_symbols
            if len(symbols) >= 2:
                names = ', '.join(str(v) for v in sorted(symbols, key=sp.default_sort_key))
                example_vars = sorted(symbols, key=sp.default_sort_key)[:2]
                a_name, b_name = map(str, example_vars)
                return [make_step(
                    eq_text(left, right),
                    f'Это уравнение содержит несколько переменных ({names}), поэтому обычно имеет бесконечно много решений. '
                    f'Чтобы найти конкретные значения, добавьте ещё одно независимое уравнение через «;», например: '
                    f'{a_name} + {b_name} = 5; {a_name} - {b_name} = 1.',
                )], 'бесконечно много решений (зависит от нескольких переменных)'
            equal = sp.simplify(left - right) == 0
            answer_text = 'верно' if equal else 'неверно'
            return [make_step(
                eq_text(left, right),
                f'Проверяем равенство: {answer_text}.',
            )], answer_text
        return [make_step(
            f'{compact(left)} {op} {compact(right)}',
            'В выражении больше одной переменной, поэтому сравнение не сводится к одному числу.',
        )], 'не определено'

    if op != '=':
        return inequality_steps(op, left, right, var)

    expr = sp.expand(left - right)
    if expr.is_polynomial(var):
        poly = sp.Poly(expr, var)
        if poly.degree() == 1:
            result = linear_equation_steps(left, right, var)
            if result:
                return result
        if poly.degree() == 2:
            result = quadratic_equation_steps(left, right, var)
            if result:
                return result

    return generic_equation_steps(left, right, var)

def build_step_clarification(formula, explanation, original_task, step_number):
    """Создаёт дополнительное пояснение к выбранному шагу без обращения к сети/ИИ."""
    f = formula.lower()
    e = explanation.lower()
    parts = [
        f'Исходная задача: {original_task}',
        f'Выбранный шаг {step_number}: {formula}',
        '',
        'Что происходит на этом этапе:',
        explanation or 'На этом этапе записан промежуточный результат решения.',
        '',
        'Подробное пояснение:',
    ]

    if 'одз' in f or 'область допустимых' in e:
        parts.append(
            'ОДЗ — область допустимых значений. Это все значения переменной, '
            'при которых исходное выражение имеет смысл. Например, аргумент '
            'логарифма должен быть положительным: ноль и отрицательные числа '
            'под логарифмом не допускаются. Поэтому найденные далее значения '
            'нужно проверить по этому условию.'
        )
    elif 'дискриминант' in e or re.search(r'\bD\s*=', formula):
        parts.append(
            'Для квадратного уравнения сначала определяют коэффициенты a, b и c '
            'в записи ax² + bx + c = 0. Затем подставляют их в формулу '
            'D = b² − 4ac. Если D > 0, есть два действительных корня; если D = 0, '
            'корень один (двукратный); если D < 0, действительных корней нет. '
            'Важно подставлять коэффициенты вместе с их знаками.'
        )
    elif 'перенос' in e or 'противоположным знаком' in e:
        parts.append(
            'При переносе слагаемого через знак равенства его знак меняется на '
            'противоположный. Это равносильно прибавлению или вычитанию одного '
            'и того же выражения из обеих частей уравнения, поэтому равенство '
            'сохраняется. После переноса удобно привести подобные слагаемые.'
        )
    elif 'делим' in e or 'деление' in e:
        parts.append(
            'Чтобы оставить неизвестную отдельно, обе части уравнения делят '
            'на один и тот же коэффициент. Равенство при этом сохраняется, '
            'если делитель не равен нулю. Затем выполняют получившееся деление '
            'и записывают значение переменной.'
        )
    elif 'тригонометр' in e or 'период' in e or 'k ∈' in formula:
        parts.append(
            'Тригонометрические функции периодические: их значения повторяются '
            'через определённый промежуток. Поэтому одного или нескольких углов '
            'на одном промежутке недостаточно — нужно записать общее решение. '
            'Буква k обозначает любое целое число (…, −2, −1, 0, 1, 2, …), '
            'а добавление периода учитывает все подходящие углы.'
        )
    elif 'систем' in e or 'систем' in f:
        parts.append(
            'В системе все уравнения должны выполняться одновременно. Поэтому '
            'пара значений считается решением только тогда, когда она подходит '
            'каждому уравнению системы, а не только одному из них.'
        )
    elif 'подстав' in e:
        parts.append(
            'Подстановка означает, что буквенные коэффициенты в формуле заменяют '
            'их конкретными значениями из условия или предыдущего шага. После '
            'этого вычисления выполняют по порядку действий, сохраняя скобки '
            'и знаки чисел.'
        )
    elif 'ответ:' in f or 'итоговый ответ' in e or 'корней' in e:
        parts.append(
            'Это итоговая запись результата. Для уравнения указываются значения '
            'переменной, для неравенства — промежутки или объединение промежутков, '
            'для системы — пары значений. Если решение содержит параметр k, '
            'он принимает любые целые значения.'
        )
    elif 'неравенств' in e or any(ch in formula for ch in '≤≥'):
        parts.append(
            'Ответ неравенства — не одно число, а множество всех значений '
            'переменной, при которых исходное сравнение верно. Круглая скобка '
            'означает, что граница не входит в промежуток, квадратная — что '
            'граница входит.'
        )
    elif 'квадратн' in e or 'корн' in e:
        parts.append(
            'На этом этапе используется правило решения квадратного уравнения. '
            'Каждое преобразование должно сохранять равносильность исходному '
            'уравнению; найденные корни в конце желательно подставить обратно '
            'в исходную запись.'
        )
    else:
        parts.append(
            'Сначала прочитайте формулу как запись текущего промежуточного '
            'результата, затем сопоставьте её с пояснением под шагом. Каждый '
            'следующий шаг должен следовать из предыдущего по известному '
            'математическому правилу. Для окончательной проверки подставьте '
            'полученный результат в исходное условие, если такая проверка применима.'
        )

    parts.extend([
        '',
        'На что обратить внимание:',
        '• сохраняйте знаки «плюс» и «минус» при переносе и подстановке;',
        '• не делите на выражение, которое может быть равно нулю, без проверки;',
        '• проверяйте найденные значения в исходной задаче и учитывайте ОДЗ.'
    ])
    return '\n'.join(parts)



def solve_for_web(text):
    try:
        steps, answer = solve_problem(text)
        return {"answer": str(answer), "steps": [{"formula": str(a), "explanation": str(b)} for a, b in steps]}
    except Exception as exc:
        message = str(exc)
        if 'invalid syntax' in message or 'could not parse' in message.lower():
            message = ('Не удалось разобрать запись. Для тригонометрии используй, например: '
                       'sin(x)=0, cos(2x)=1, tg(x)=1 или sin²(x)=1. '
                       'Аргументы вводи в радианах; умножение можно писать как 2x.')
        raise ValueError(message) from None

