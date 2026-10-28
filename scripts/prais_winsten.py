"""Regressão de Prais-Winsten e variação percentual anual (VPA), como no artigo Bastos et al. 2026
(Antunes e Cardoso, 2015): log10(y) = a + b*ano, com erro AR(1) estimado de forma iterativa; VPA = (10^b - 1) * 100.
Puro Python, sem bibliotecas. O valor crítico t (bicaudal, 95%) vem de uma tabela pequena porque o artigo usa séries
anuais curtas (2010-2023 = 14 pontos, 12 graus de liberdade)."""
import math

# t de Student, bicaudal 95%, por graus de liberdade (n - 2) das séries anuais usadas no projeto
T95 = {3: 3.182446, 4: 2.776445, 5: 2.570582, 6: 2.446912, 7: 2.364624, 8: 2.306004, 9: 2.262157, 10: 2.228139,
       11: 2.200985, 12: 2.178813, 13: 2.160369, 14: 2.144787}


def _ajustar(x, ly, rho):
    n = len(ly)
    w = math.sqrt(1 - rho * rho)
    ys = [ly[0] * w] + [ly[i] - rho * ly[i - 1] for i in range(1, n)]
    c = [w] + [1 - rho] * (n - 1)
    t = [x[0] * w] + [x[i] - rho * x[i - 1] for i in range(1, n)]
    scc = sum(a * a for a in c)
    sct = sum(a * b for a, b in zip(c, t))
    stt = sum(b * b for b in t)
    scy = sum(a * b for a, b in zip(c, ys))
    sty = sum(a * b for a, b in zip(t, ys))
    det = scc * stt - sct * sct
    a = (scy * stt - sty * sct) / det
    b = (sty * scc - scy * sct) / det
    res = [ys[i] - a * c[i] - b * t[i] for i in range(n)]
    s2 = sum(r * r for r in res) / (n - 2)
    return a, b, math.sqrt(s2 * scc / det)


def prais_winsten(serie, anos=None):
    """Devolve dict com vpa, ic95_min, ic95_max, rho. A série precisa ter só valores positivos (log10)."""
    n = len(serie)
    if n < 5 or n - 2 not in T95:
        raise ValueError('série curta ou longa demais para a tabela t')
    if min(serie) <= 0:
        raise ValueError('série com valor zero ou negativo: log10 indefinido')
    x = list(anos) if anos is not None else list(range(n))
    ly = [math.log10(v) for v in serie]
    mx, my = sum(x) / n, sum(ly) / n
    b = sum((a - mx) * (c - my) for a, c in zip(x, ly)) / sum((a - mx) ** 2 for a in x)
    a = my - b * mx
    rho = 0.0
    se = 0.0
    for _ in range(500):   # como o comando prais do Stata: rho a partir dos resíduos, até convergir
        e = [ly[i] - a - b * x[i] for i in range(n)]
        r = sum(e[i] * e[i - 1] for i in range(1, n)) / sum(e[i - 1] ** 2 for i in range(1, n))
        a, b, se = _ajustar(x, ly, r)
        if abs(r - rho) < 1e-9:
            rho = r
            break
        rho = r
    t = T95[n - 2]
    return {'vpa': (10 ** b - 1) * 100, 'ic95_min': (10 ** (b - t * se) - 1) * 100,
            'ic95_max': (10 ** (b + t * se) - 1) * 100, 'rho': rho}
