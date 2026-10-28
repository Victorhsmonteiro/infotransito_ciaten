"""Confere a base de dados do painel contra o artigo de referência (Bastos et al., Rev Bras Epidemiol 2026) e contra as
fontes oficiais que o próprio artigo cita: SIH/SUS e SIM (TABNET/DATASUS), população do IBGE e índice IGP-M (Banco Central).
Só consulta essas fontes; nada de PRF, OpenStreetMap ou outras bases.

Etapas:
  1. artigo x base: cada número das Tabelas 1 a 4 do artigo contra data/sinistros.json (offline);
  2. consistência interna do artigo (somas, razões, médias);
  3. TABNET: reproduz totais, séries anuais, letalidade, custo e permanência, e as VPAs por Prais-Winsten (--online);
  4. produto x TABNET/IBGE: óbitos e internações 2020-2024 por região de saúde e população (--online);
  5. código do painel x composição oficial das macrorregiões de saúde.
Uso: python scripts/verificar_base.py [--online]
Grava data/verificacao_base.json e VERIFICACAO_BASE.md."""
import datetime, json, os, re, sys, unicodedata, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prais_winsten import prais_winsten   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SINISTROS = os.path.join(ROOT, 'data', 'sinistros.json')
ONLINE = '--online' in sys.argv
GRUPOS = [str(i) for i in range(1, 10)]   # V01-V89

# ---------------------------------------------------------------- tabelas do artigo (transcritas do PDF, em inglês)
TABELA_1 = """Piauí 176.1 5.72 (1.04; 10.61) 0.020 Increasing
Men 292.6 5.71 (0.92; 10.71) 0.023 Increasing
Women 65.9 6.13 (1.77; 10.69) 0.009 Increasing
0–9 24.5 5.20 (-2.66; 13.70) 0.180 Stationary
10–19 124.8 4.56 (-0.79; 10.19) 0.089 Stationary
20–39 279.1 4.30 (0.03; 8.74) 0.048 Increasing
40–59 200.6 7.54 (2.75; 12.55) 0.005 Increasing
60 or over 112.8 8.47 (2.40; 14.90) 0.010 Increasing
Pedestrian 12.6 -0.60 (-11.50; 11.64) 0.912 Stationary
Cyclist 4.3 13.73 (2.05; 26.74) 0.024 Increasing
Motorcyclist 151.2 5.76 (1.32; 10.39) 0.015 Increasing
Vehicle occupant 4.7 11.07 (-0.64; 24.16) 0.063 Stationary
Others 3.3 6.60 (-3.53; 17.8) 0.188 Stationary
Carnaubais 272.6 12.92 (1.05; 26.19) 0.035 Increasing
Chapada das Mangabeiras 171 3.50 (-2.96; 10.39) 0.267 Stationary
Cocais 110.1 3.41 (-2.94; 10.17) 0.271 Stationary
Entre Rios 230.7 8.52 (2.13; 15.31) 0.012 Increasing
Planície Litorânea 84.4 -1.34 (-24.14; 28.32) 0.913 Stationary
Serra da Capivara 181.9 7.44 (5.65; 9.26) <0.001 Increasing
Tabuleiros do Alto Parnaíba 243.1 10.63 (4.04; 17.62) 0.004 Increasing
Vale do Canindé 171.2 -2.64 (-6.62; 1.52) 0.189 Stationary
Vale do Rio Guaribas 83.8 -13.84 (-19.29; -8.03) <0.001 Decreasing
Vale do Sambito 122 -1.29 (-10.03; 8.29) 0.765 Stationary
Vale dos Rios Piauí e Itaueiras 227.2 7.17 (4.24; 10.17) 0.001 Increasing
Chapada Vale do Rio Itaim 54.2 -11.38 (-20.04; -1.78) 0.025 Decreasing
Semi-arid 100.1 -7.20 (-11.62; -2.56) 0.006 Decreasing
Mid North 235.6 9.03 (2.05; 16.49) 0.015 Increasing
Coastline 99.5 3.92 (-4.66; 13.27) 0.350 Stationary
Cerrado 199.5 6.23 (4.72; 7.76) <0.001 Increasing"""

TABELA_2 = """Piauí 2.3 -2.42 (-5.07; 0.30) 0.076 Stationary
Men 2.5 -2.38 (-5.15; 0.48) 0.094 Stationary
Women 1.6 -2.11 (-4.60; 0.44) 0.096 Stationary
0–9 1.4 -0.65 (-7.76; 7.02) 0.853 Stationary
10–19 1.7 -0.93 (-5.52; 3.88) 0.675 Stationary
20–39 2.1 -2.99 (-5.58; -0.33) 0.031 Decreasing
40–59 2.3 -2.55 (-2.55; 0.60) 0.103 Stationary
60 or over 5.1 -5.36 (-8.14; -2.50) 0.002 Decreasing
Pedestrian 2.4 4.33 (-5.96; 15.75) 0.391 Stationary
Cyclist 2.4 1.82 (-8.25; 12.99) 0.713 Stationary
Motorcyclist 2.3 -2.93 (-6.05; 0.29) 0.071 Stationary
Vehicle occupant 3.6 4.40 (-5.89; 15.82) 0.384 Stationary
Others 2.1 -5.69 (-16.93; 7.06) 0.334 Stationary
Carnaubais 2.1 -5.95 (-12.19; 0.72) 0.075 Stationary
Chapada das Mangabeiras 1.7 1.41 (-6.73; 10.25) 0.722 Stationary
Cocais 3.6 1.07 (-2.82; 5.12) 0.566 Stationary
Entre Rios 2.1 -5.34 (-8.75; -1.81) 0.007 Decreasing
Planície Litorânea 1.3 -10.5 (-20.98; 1.38) 0.076 Stationary
Serra da Capivara 2.5 10.42 (0.02; 21.91) 0.050 Stationary
Tabuleiros do Alto Parnaíba 1.7 -1.49 (-8.19; 5.70) 0.651 Stationary
Vale do Canindé 1.9 1.25 (-7.87; 11.28) 0.779 Stationary
Vale do Rio Guaribas 5.1 9.04 (-3.19; 22.81) 0.139 Stationary
Vale do Sambito 3.6 -1.05 (-6.43; 4.65) 0.689 Stationary
Vale dos Rios Piauí e Itaueiras 1.8 0.86 (-3.94; 5.91) 0.709 Stationary
Chapada Vale do Rio Itaim 4.8 -1.35 (-15.08; 14.59) 0.846 Stationary
Semi-arid 3.7 2.86 (-7.84; 14.80) 0.586 Stationary
Mid North 2.1 -5.21 (-8.92; -1.36) 0.013 Decreasing
Coastline 2.8 -0.03 (-4.05; 4.16) 0.988 Stationary
Cerrado 1.9 3.17 (-0.53; 7.01) 0.087 Stationary"""

TABELA_3 = """Piauí 1,123.92 -3.17 (-5.57; -0.71) 0.016 Decreasing
Men 1,151.85 -3.00 (-5.43; -0.52) 0.022 Decreasing
Women 1,006.70 -3.90 (-6.20; -1.54) 0.004 Decreasing
0–9 958.08 -3.44 (-6.47; -0.31) 0.034 Decreasing
10–19 1,110.28 -4.31 (-6.80; -1.76) 0.003 Decreasing
20–39 1,126.98 -2.82 (-5.28; -0.29) 0.032 Decreasing
40–59 1,118.48 -3.23 (-5.38; -1.03) 0.008 Decreasing
60 or over 1,187.77 -3.22 (-6.09; -0.26) 0.035 Decreasing
Pedestrian 974.28 -4.53 (-14.18; 6.21) 0.362 Stationary
Cyclist 984.04 0.80 (-1.02; 2.64) 0.360 Stationary
Motorcyclist 1,132.64 -2.96 (-5.14; -0.73) 0.014 Decreasing
Vehicle occupant 1,258.30 2.51 (-1.50; 6.68) 0.201 Stationary
Others 1,283.86 -8.28 (-15.15; -0.85) 0.032 Decreasing
Semi-arid 1,191.10 -1.29 (-5.60; 3.21) 0.537 Stationary
Mid North 1,155.13 -3.69 (-6.89; -0.38) 0.032 Decreasing
Coastline 1,124.11 -7.03 (-11.80; -2.00) 0.011 Decreasing
Cerrado 1,005.40 -2.15 (-3.66; -0.62) 0.010 Decreasing"""

TABELA_4 = """Piauí 4.9 -1.07 (-2.96; 0.86) 0.248 Stationary
Men 4.9 -1.00 (-2.92; 0.96) 0.287 Stationary
Women 4.6 -1.38 (-3.21; 0.48) 0.130 Stationary
0–9 3.6 -2.26 (-3.29; -1.22) 0.001 Decreasing
10–19 4.7 -1.57 (-2.99; -0.13) 0.035 Decreasing
20–39 4.8 -1.22 (-3.04; 0.62) 0.173 Stationary
40–59 5.1 -1.36 (-3.50; 0.82) 0.198 Stationary
60 or over 5.5 -1.12 (-3.19; 0.98) 0.266 Stationary
Pedestrian 5.4 -0.9 (-2.05; 0.27) 0.119 Stationary
Cyclist 4.2 -1.05 (-3.96; 1.93) 0.453 Stationary
Motorcyclist 4.8 -1.12 (-3.29; 1.10) 0.290 Stationary
Vehicle occupant 5.7 5.84 (1.15; 10.74) 0.018 Increasing
Others 6.3 -2.9 (-5.74; 0.02) 0.051 Stationary
Semi-arid 5.3 1.42 (0.06; 2.81) 0.042 Increasing
Mid North 4.2 -2.90 (-6.69; 1.05) 0.134 Stationary
Coastline 5.8 -0.93 (-2.27; 0.42) 0.159 Stationary
Cerrado 6.0 1.96 (0.10; 3.85) 0.040 Increasing"""

# rótulo do artigo -> (grupo no JSON, chave no JSON)
ROTULOS = {
    'Piauí': ('geral', None), 'Men': ('por_sexo', 'masculino'), 'Women': ('por_sexo', 'feminino'),
    '0–9': ('por_faixa_etaria', '0_a_9_anos'), '10–19': ('por_faixa_etaria', '10_a_19_anos'),
    '20–39': ('por_faixa_etaria', '20_a_39_anos'), '40–59': ('por_faixa_etaria', '40_a_59_anos'),
    '60 or over': ('por_faixa_etaria', '60_anos_ou_mais'),
    'Pedestrian': ('por_tipo_vitima', 'pedestre'), 'Cyclist': ('por_tipo_vitima', 'ciclista'),
    'Motorcyclist': ('por_tipo_vitima', 'motociclista'), 'Vehicle occupant': ('por_tipo_vitima', 'ocupante_de_veiculo'),
    'Others': ('por_tipo_vitima', 'outros'),
    'Semi-arid': ('por_macrorregiao', 'semiarido'), 'Mid North': ('por_macrorregiao', 'meio_norte'),
    'Coastline': ('por_macrorregiao', 'litoral'), 'Cerrado': ('por_macrorregiao', 'cerrado'),
}
TENDENCIA = {'Increasing': 'Crescente', 'Decreasing': 'Decrescente', 'Stationary': 'Estável'}
SECOES = {'Tabela 1 (taxa de internação)': ('taxa_internacao_hospitalar_100mil_hab', TABELA_1),
          'Tabela 2 (letalidade hospitalar)': ('letalidade_hospitalar_pct', TABELA_2),
          'Tabela 3 (valor médio por internação)': ('valor_medio_internacao_reais', TABELA_3),
          'Tabela 4 (permanência média)': ('permanencia_media_dias', TABELA_4)}

RESULTADOS = []


def registrar(grupo, descricao, esperado, obtido, status, nota=''):
    RESULTADOS.append({'grupo': grupo, 'descricao': descricao, 'esperado': esperado, 'obtido': obtido, 'status': status, 'nota': nota})


def slug(s):
    s = ''.join(c for c in unicodedata.normalize('NFD', s.lower()) if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9]+', '_', s).strip('_')


def linhas_da_tabela(texto):
    padrao = re.compile(r'^(.+?)\s+(-?[\d.,]+)\s+(-?[\d.]+) \((-?[\d.]+); (-?[\d.]+)\)\s+(<?[\d.]+)\s+(Increasing|Decreasing|Stationary)$')
    for lin in texto.splitlines():
        m = padrao.match(lin.strip())
        assert m, 'linha da tabela não reconhecida: ' + lin
        rot, val, vpa, lo, hi, p, tend = m.groups()
        yield rot, float(val.replace(',', '')), float(vpa), float(lo), float(hi), p, tend


def caminho(estudo, bloco, rot):
    """Localiza o dict do JSON que corresponde ao rótulo da tabela (regiões de saúde pelo nome em slug)."""
    if rot in ROTULOS:
        g, k = ROTULOS[rot]
        return estudo[bloco][g] if k is None else estudo[bloco][g][k]
    return estudo[bloco].get('por_regiao_de_saude', {}).get(slug(rot))


# ---------------------------------------------------------------- 1. artigo x base
def conferir_artigo(estudo):
    for titulo, (bloco, texto) in SECOES.items():
        n_ok = 0
        for rot, val, vpa, lo, hi, p, tend in linhas_da_tabela(texto):
            j = caminho(estudo, bloco, rot)
            if j is None:
                registrar('artigo x base', f'{titulo}: {rot}', 'presente no JSON', 'ausente', 'divergente')
                continue
            erros = []
            for nome, a, b, tol in (('valor', val, j['valor'], 0.005), ('VPA', vpa, j['vpa_pct'], 0.005), ('IC95 mín.', lo, j['ic95_min'], 0.005),
                                    ('IC95 máx.', hi, j['ic95_max'], 0.005)):
                if abs(a - b) > tol:
                    erros.append(f'{nome}: artigo {a} x base {b}')
            p_art = 0.001 if p.startswith('<') else float(p)
            if abs(p_art - j['valor_p']) > 0.0005:
                erros.append(f'p: artigo {p} x base {j["valor_p"]}')
            if TENDENCIA[tend] != j['tendencia']:
                erros.append(f'tendência: artigo {tend} x base {j["tendencia"]}')
            if erros:
                registrar('artigo x base', f'{titulo}: {rot}', 'igual ao artigo', '; '.join(erros), 'divergente')
            else:
                n_ok += 1
        registrar('artigo x base', f'{titulo}: linhas conferidas', 'todas iguais', f'{n_ok} linhas idênticas ao artigo', 'ok')
    # regiões de saúde das Tabelas 3 e 4 não existem no artigo: a base também não deve ter
    registrar('artigo x base', 'Tabelas 3 e 4 não trazem região de saúde', 'base sem custo/permanência por região',
              'ok' if 'por_regiao_de_saude' not in estudo['valor_medio_internacao_reais'] else 'base tem região', 'ok')
    rot_tot = [('total de internações', 80251, estudo['total_internacoes_periodo']), ('óbitos hospitalares', 1866, estudo['letalidade_hospitalar_pct']['obitos_hospitalares_totais_periodo']),
               ('total pago (R$)', 90200000, estudo['valor_medio_internacao_reais']['valor_total_periodo_reais']),
               ('total corrigido IGP-M (R$)', 128000000, estudo['valor_medio_internacao_reais']['valor_total_periodo_corrigido_igpm_reais']),
               ('valor médio corrigido (R$)', 1659.40, estudo['valor_medio_internacao_reais']['valor_medio_corrigido_igpm_reais']),
               ('dias de permanência', 392047, estudo['permanencia_media_dias']['total_dias_periodo']),
               ('população 2022', 3271199, estudo['contexto_estado_piaui']['populacao']),
               ('ano com mais internações', 2016, estudo['ano_com_mais_internacoes']['ano']), ('internações em 2016', 7478, estudo['ano_com_mais_internacoes']['internacoes']),
               ('taxa em 2016', 230.3, estudo['ano_com_mais_internacoes']['taxa_100mil']), ('ano com menos internações', 2012, estudo['ano_com_menos_internacoes']['ano']),
               ('internações em 2012', 2950, estudo['ano_com_menos_internacoes']['internacoes']), ('taxa em 2012', 91.8, estudo['ano_com_menos_internacoes']['taxa_100mil'])]
    for nome, a, b in rot_tot:
        registrar('artigo x base', f'Texto do artigo: {nome}', a, b, 'ok' if a == b else 'divergente')
    cit = estudo['citacao']
    doc_ok = 'doi.org' not in cit and re.search(r'DOI: 10\.1590/1980-549720260044\.?$', cit) and not cit.endswith('.2')
    registrar('artigo x base', 'DOI na citação (artigo: 10.1590/1980-549720260044)', '10.1590/1980-549720260044', cit[-34:],
              'ok' if doc_ok else 'divergente', 'o sufixo ".2" não existe no DOI do artigo' if not doc_ok else '')


# ---------------------------------------------------------------- 2. consistência interna do artigo
def consistencia_interna(estudo):
    t = estudo['taxa_internacao_hospitalar_100mil_hab']
    soma = sum(v['valor'] for v in t['por_tipo_vitima'].values())
    registrar('consistência do artigo', 'Soma das taxas por tipo de vítima = taxa geral (176,1)', 176.1, round(soma, 1), 'ok' if abs(soma - 176.1) < 0.05 else 'divergente')
    r = t['por_sexo']['masculino']['valor'] / t['por_sexo']['feminino']['valor']
    registrar('consistência do artigo', 'Razão homem/mulher (texto: 4,4 vezes)', 4.4, round(r, 2), 'ok' if abs(r - 4.4) < 0.05 else 'divergente')
    r = t['por_tipo_vitima']['motociclista']['valor'] / t['por_tipo_vitima']['pedestre']['valor']
    registrar('consistência do artigo', 'Razão motociclista/pedestre (texto: 12 vezes)', 12, round(r, 1), 'ok' if abs(r - 12) < 0.1 else 'divergente')
    n, ob = estudo['total_internacoes_periodo'], estudo['letalidade_hospitalar_pct']['obitos_hospitalares_totais_periodo']
    registrar('consistência do artigo', 'Óbitos / internações = letalidade 2,3%', 2.3, round(ob / n * 100, 2), 'ok' if abs(ob / n * 100 - 2.3) < 0.05 else 'divergente')
    v = estudo['valor_medio_internacao_reais']
    media = v['valor_total_periodo_reais'] / n
    registrar('consistência do artigo', 'Total pago / internações = valor médio (R$ 1.123,92)', 1123.92, round(media, 2),
              'ok' if abs(media - 1123.92) < 5 else 'divergente', 'R$ 90,2 milhões é arredondado; a diferença é do arredondamento')
    media_corr = v['valor_total_periodo_corrigido_igpm_reais'] / n
    registrar('consistência do artigo', 'Total corrigido (R$ 128,0 mi) / internações = valor médio corrigido (R$ 1.659,40)', 1659.40, round(media_corr, 2),
              'ok' if abs(media_corr - 1659.40) < 5 else 'aviso',
              'o artigo diz R$ 1.659,40, mas R$ 128,0 mi / 80.251 dá R$ 1.595: os dois valores corrigidos não são compatíveis entre si')
    dias = estudo['permanencia_media_dias']['total_dias_periodo'] / n
    registrar('consistência do artigo', 'Dias / internações = permanência média 4,9', 4.9, round(dias, 2), 'ok' if abs(dias - 4.9) < 0.05 else 'divergente')
    lt = estudo['letalidade_hospitalar_pct']['por_faixa_etaria']['40_a_59_anos']
    registrar('consistência do artigo', 'Tabela 2, 40–59 anos: limite inferior do IC95 igual à própria VPA', 'IC95 mín. < VPA < IC95 máx.',
              f'VPA {lt["vpa_pct"]} (IC95 {lt["ic95_min"]}; {lt["ic95_max"]})', 'aviso',
              'o artigo imprime -2,55 (-2,55; 0,60): provável erro de digitação do limite inferior (a VPA fica no centro do IC em escala log, o que daria algo perto de -5,6). A base repete o número do artigo; trate como não confiável')


# ---------------------------------------------------------------- fontes online
def baixar(url, dados=None):
    import importar_saude_vias as isv
    return isv.baixar(url, dados)


def num(v):
    v = v.strip()
    return 0.0 if v in ('-', '', '...') else float(v.replace('.', '').replace(',', '.')) if ',' in v else float(v.replace('.', ''))


def serie_tabnet(isv, linha, incremento, arquivos):
    """Linha x ano de processamento -> {rótulo: [valores por ano]}; o último item da tabela é o Total."""
    t = isv.tabnet('sih/cnv/frpi.def', {'Linha': [linha], 'Coluna': ['Ano_processamento'], 'Incremento': [incremento],
                                          'Arquivos': arquivos, 'SGrupo_de_Causas': GRUPOS})
    anos = [int(a) for a in t[0][1:-1]]
    return anos, {r[0]: [num(x) for x in r[1:-1]] for r in t[1:]}


def aproximado(esp, obt, tol):
    return abs(esp - obt) <= tol


def conferir_datasus(estudo):
    import importar_saude_vias as isv
    arq = [f'frpi{a:02d}{m:02d}.dbf' for a in range(10, 24) for m in range(1, 13)]   # jan/2010 a dez/2023, como no artigo
    anos, I = serie_tabnet(isv, 'Região_de_Saúde_(CIR)', 'Internações', arq)
    _, O = serie_tabnet(isv, 'Região_de_Saúde_(CIR)', 'Óbitos', arq)
    _, V = serie_tabnet(isv, 'Região_de_Saúde_(CIR)', 'Valor_total', arq)
    _, D = serie_tabnet(isv, 'Região_de_Saúde_(CIR)', 'Dias_permanência', arq)
    # a linha Total vem com a soma no último campo; recalcula a partir das regiões para não depender dela
    regs = [r for r in I if r != 'Total']
    soma = lambda S: [sum(S[r][i] for r in regs) for i in range(len(anos))]  # noqa: E731
    Ipi, Opi, Vpi, Dpi = soma(I), soma(O), soma(V), soma(D)
    ST = 'TABNET SIH/SUS (frpi, residência, V01-V89, arquivos jan/2010-dez/2023)'
    for nome, esp, obt, tol in (('total de internações', 80251, sum(Ipi), 0), ('óbitos hospitalares', 1866, sum(Opi), 0),
                                ('total pago (R$)', 90200000, sum(Vpi), 50000), ('dias de permanência', 392047, sum(Dpi), 0)):
        registrar(ST, f'Total: {nome}', esp, round(obt, 2), 'ok' if aproximado(esp, obt, tol) else 'divergente')
    tab_ano = isv.tabnet('sih/cnv/frpi.def', {'Linha': ['Ano_processamento'], 'Coluna': ['--Não-Ativa--'], 'Incremento': ['Internações'],
                                               'Arquivos': arq, 'SGrupo_de_Causas': GRUPOS})
    por_ano = {int(r[0]): num(r[1]) for r in tab_ano[1:] if r[0] != 'Total'}
    e = estudo
    registrar(ST, 'Ano com mais internações (ano de processamento)', f'2016 = {e["ano_com_mais_internacoes"]["internacoes"]}',
              f'2016 = {int(por_ano[2016])}', 'ok' if por_ano[2016] == e['ano_com_mais_internacoes']['internacoes'] and max(por_ano, key=por_ano.get) == 2016 else 'divergente')
    registrar(ST, 'Ano com menos internações (ano de processamento)', f'2012 = {e["ano_com_menos_internacoes"]["internacoes"]}',
              f'2012 = {int(por_ano[2012])}', 'ok' if por_ano[2012] == e['ano_com_menos_internacoes']['internacoes'] and min(por_ano, key=por_ano.get) == 2012 else 'divergente',
              'o artigo usa o ano de processamento da AIH, não o ano do atendimento')

    # macrorregiões oficiais
    t = isv.tabnet('sih/cnv/frpi.def', {'Linha': ['Macrorregião_de_Saúde'], 'Coluna': ['Região_de_Saúde_(CIR)'], 'Incremento': ['Internações'],
                                         'Arquivos': arq, 'SGrupo_de_Causas': GRUPOS})
    nomes_macro = {'SEMI-ARIDO': 'semiarido', 'MEIO NORTE': 'meio_norte', 'LITORAL': 'litoral', 'CERRADOS': 'cerrado'}
    macro_de = {}
    for lin in t[1:]:
        if lin[0] == 'Total':
            continue
        chave = nomes_macro[lin[0].split(' ', 1)[1]]
        for i, v in enumerate(lin[1:-1], 1):
            if num(v):
                macro_de[slug(t[0][i][6:])] = chave
    OFICIAL = macro_de
    macros = {}
    for r in regs:
        macros.setdefault(macro_de[slug(r[6:])], []).append(r)

    def agrega(S, rs):
        return [sum(S[r][i] for r in rs) for i in range(len(anos))]

    # valores e VPAs, por estrato: Piauí, 12 regiões, 4 macrorregiões
    def verificar(bloco, tabela, razao, estratos, comparar_vpa=True, casas=2):
        for rot, rs in estratos:
            j = caminho(e, bloco, rot) if rot != 'Piauí' else e[bloco]['geral']
            if j is None:
                continue
            num_, den_ = razao(rs)
            esp = j['valor']
            obt = sum(num_) / sum(den_) * (100 if bloco == 'letalidade_hospitalar_pct' else 1)
            tol = {'letalidade_hospitalar_pct': 0.05, 'valor_medio_internacao_reais': 0.01, 'permanencia_media_dias': 0.05}[bloco]
            ok = abs(esp - obt) <= tol + 1e-9
            registrar(ST, f'{tabela} — valor: {rot}', esp, round(obt, 2), 'ok' if ok else 'divergente')
            if not comparar_vpa:
                continue
            serie = [a / b * (100 if bloco == 'letalidade_hospitalar_pct' else 1) for a, b in zip(num_, den_)]
            try:
                pw = prais_winsten(serie, anos)
            except ValueError as err:
                registrar(ST, f'{tabela} — VPA: {rot}', f'{j["vpa_pct"]} ({j["ic95_min"]}; {j["ic95_max"]})', 'não calculável',
                          'nao_reproduzido', f'{err} (há anos sem óbitos); o artigo não explica como tratou esses zeros')
                continue
            bate = abs(pw['vpa'] - j['vpa_pct']) <= 0.02 and abs(pw['ic95_min'] - j['ic95_min']) <= 0.03 and abs(pw['ic95_max'] - j['ic95_max']) <= 0.03
            registrar(ST, f'{tabela} — VPA (Prais-Winsten): {rot}', f'{j["vpa_pct"]} ({j["ic95_min"]}; {j["ic95_max"]})',
                      f'{pw["vpa"]:.2f} ({pw["ic95_min"]:.2f}; {pw["ic95_max"]:.2f})', 'ok' if bate else 'divergente')

    estratos = [('Piauí', regs)] + [(r[6:], [r]) for r in regs] + [(rot, macros[k]) for rot, k in
                                                                    (('Semi-arid', 'semiarido'), ('Mid North', 'meio_norte'), ('Coastline', 'litoral'), ('Cerrado', 'cerrado'))]
    # letalidade: valores e VPA em todos os estratos
    verificar('letalidade_hospitalar_pct', 'Tabela 2 letalidade', lambda rs: (agrega(O, rs), agrega(I, rs)), estratos)
    # custo médio: valores nominais batem; a VPA do artigo vem de valores corrigidos (verificada à parte, abaixo)
    macro_estratos = [x for x in estratos if x[0] in ('Piauí', 'Semi-arid', 'Mid North', 'Coastline', 'Cerrado')]
    verificar('valor_medio_internacao_reais', 'Tabela 3 valor médio', lambda rs: (agrega(V, rs), agrega(I, rs)), macro_estratos, comparar_vpa=False)
    verificar('permanencia_media_dias', 'Tabela 4 permanência', lambda rs: (agrega(D, rs), agrega(I, rs)), macro_estratos)

    # por sexo (letalidade, custo, permanência)
    def serie_sexo(inc):
        return serie_tabnet(isv, 'Sexo', inc, arq)[1]
    Is, Os, Vs, Ds = (serie_sexo(x) for x in ('Internações', 'Óbitos', 'Valor_total', 'Dias_permanência'))
    sx = {'Men': next(k for k in Is if k.lower().startswith('masc')), 'Women': next(k for k in Is if k.lower().startswith('fem'))}
    for rot, k in sx.items():
        for bloco, tabela, N, Dn in (('letalidade_hospitalar_pct', 'Tabela 2 letalidade', Os, Is), ('valor_medio_internacao_reais', 'Tabela 3 valor médio', Vs, Is),
                                     ('permanencia_media_dias', 'Tabela 4 permanência', Ds, Is)):
            j = caminho(e, bloco, rot)
            obt = sum(N[k]) / sum(Dn[k]) * (100 if bloco == 'letalidade_hospitalar_pct' else 1)
            tol = {'letalidade_hospitalar_pct': 0.05, 'valor_medio_internacao_reais': 0.01, 'permanencia_media_dias': 0.05}[bloco]
            registrar(ST, f'{tabela} — valor por sexo: {rot}', j['valor'], round(obt, 2), 'ok' if abs(obt - j['valor']) <= tol + 1e-9 else 'divergente')

    # taxa de internação: população do Censo 2022 (IBGE) como aproximação das projeções anuais do Ministério da Saúde
    pop = {}
    s = json.load(open(os.path.join(ROOT, 'data', 'saude_municipios.json'), encoding='utf-8'))
    for m in s['municipios'].values():
        k = slug(m['regiao_de_saude'][6:])
        pop[k] = pop.get(k, 0) + m['populacao_2022']
    for r in regs:
        j = e['taxa_internacao_hospitalar_100mil_hab']['por_regiao_de_saude'][slug(r[6:])]
        aprox = sum(I[r]) / len(anos) / pop[slug(r[6:])] * 1e5
        razao = aprox / j['valor']
        registrar('TABNET + IBGE: taxa de internação (aproximada)', f'Tabela 1 — {r[6:]}', j['valor'], round(aprox, 1),
                  'ok' if abs(razao - 1) <= 0.10 else 'divergente',
                  f'razão {razao:.2f}; aproximação com a população do Censo 2022 (o artigo usa as projeções anuais do Ministério da Saúde)')
    aprox = sum(Ipi) / len(anos) / sum(pop.values()) * 1e5
    registrar('TABNET + IBGE: taxa de internação (aproximada)', 'Tabela 1 — Piauí', 176.1, round(aprox, 1), 'ok' if abs(aprox / 176.1 - 1) <= 0.05 else 'divergente')

    # custo corrigido: IGP-M do Banco Central (série SGS 189)
    ig = json.loads(baixar('https://api.bcb.gov.br/dados/serie/bcdata.sgs.189/dados?formato=json&dataInicial=01/01/2009&dataFinal=31/12/2024'))
    idx, v = {}, 1.0
    for r in ig:
        _, mm, yy = r['data'].split('/')
        v *= 1 + float(r['valor']) / 100
        idx[(int(yy), int(mm))] = v
    nominal = prais_winsten([a / b for a, b in zip(Vpi, Ipi)], anos)
    j = e['valor_medio_internacao_reais']['geral']
    cenarios = []
    for base in ((2023, 12), (2024, 8), (2024, 11)):
        for ancora in (1, 6, 12):
            f = [idx[base] / idx[(a, ancora)] for a in anos]
            corr = [a * ff / b for a, ff, b in zip(Vpi, f, Ipi)]
            pw = prais_winsten(corr, anos)
            cenarios.append((base, ancora, pw['vpa'], sum(a * ff for a, ff in zip(Vpi, f)) / 1e6, sum(a * ff for a, ff in zip(Vpi, f)) / sum(Ipi)))
    registrar('TABNET + BCB (IGP-M)', 'Custo médio por internação — VPA sem correção monetária', f'{j["vpa_pct"]} (artigo, tendência decrescente)',
              f'{nominal["vpa"]:.2f} ({nominal["ic95_min"]:.2f}; {nominal["ic95_max"]:.2f})', 'aviso',
              'em valores nominais o custo médio por internação CRESCEU; a queda do artigo depende da correção pelo IGP-M')
    menor = min(c[2] for c in cenarios), max(c[2] for c in cenarios)
    registrar('TABNET + BCB (IGP-M)', 'Custo médio por internação — VPA corrigida pelo IGP-M (BCB, 9 critérios de data-base/âncora)',
              f'{j["vpa_pct"]}', f'{menor[0]:.2f} a {menor[1]:.2f}', 'nao_reproduzido',
              'o artigo não informa data-base nem mês de âncora da correção; nenhum critério testado dá exatamente -3,17')
    tmin, tmax = min(c[3] for c in cenarios), max(c[3] for c in cenarios)
    registrar('TABNET + BCB (IGP-M)', 'Total corrigido (R$ milhões) e valor médio corrigido', '128,0 mi e R$ 1.659,40',
              f'{tmin:.1f} a {tmax:.1f} mi; média R$ {min(c[4] for c in cenarios):.0f} a {max(c[4] for c in cenarios):.0f}', 'nao_reproduzido',
              'os valores corrigidos do artigo não foram reproduzidos; use o valor nominal (R$ 90,2 mi; R$ 1.123,92), que bate exatamente')

    # macrorregiões: código do painel x composição oficial
    return OFICIAL, anos, I, O, V, D, pop


def conferir_codigo_macro(oficial):
    nomes = {'meio_norte': 'Meio-Norte', 'semiarido': 'Semiárido', 'litoral': 'Litoral', 'cerrado': 'Cerrado'}
    esperado = {k: nomes[v] for k, v in oficial.items()}
    js = open(os.path.join(ROOT, 'script.js'), encoding='utf-8').read()
    bloco = re.search(r'const MACRORREGIAO_DA_REGIAO = \{(.*?)\};', js, re.S).group(1)
    atual = dict(re.findall(r"(\w+): '([^']+)'", bloco))
    erradas = {k: (atual.get(k), v) for k, v in esperado.items() if atual.get(k) != v}
    registrar('código do painel x TABNET', 'MACRORREGIAO_DA_REGIAO em script.js = composição oficial das macrorregiões', 'igual ao TABNET',
              'igual' if not erradas else '; '.join(f'{k}: painel {a} x oficial {b}' for k, (a, b) in erradas.items()), 'ok' if not erradas else 'divergente')
    py = open(os.path.join(ROOT, 'scripts', 'gerar_territorios.py'), encoding='utf-8').read()
    pares = re.findall(r"'(\w+)': \('[^']+', '(\w+)'\)", re.search(r'NOMES_REGIAO = \{(.*?)\n\}', py, re.S).group(1))
    err2 = {k: (m, oficial[k]) for k, m in pares if oficial.get(k) != m}
    registrar('código do painel x TABNET', 'NOMES_REGIAO em gerar_territorios.py = composição oficial', 'igual ao TABNET',
              'igual' if not err2 else '; '.join(f'{k}: script {a} x oficial {b}' for k, (a, b) in err2.items()), 'ok' if not err2 else 'divergente')
    registrar('artigo x TABNET', 'Composição das macrorregiões descrita no texto do artigo (Métodos)',
              'Semi-arid: Canindé, Guaribas, Capivara, Mangabeiras; Mid North: Cocais, Entre Rios, Sambito, Carnaubais; Coastline: Planície, Itaim; Cerrado: Tabuleiros, Vale dos Rios Piauí e Itaueiras',
              'oficial: Semiárido = Canindé, Guaribas, Sambito, Itaim; Meio-Norte = Carnaubais, Entre Rios; Litoral = Cocais, Planície; Cerrados = Mangabeiras, Capivara, Tabuleiros, Vale dos Rios Piauí e Itaueiras',
              'aviso', 'os números das Tabelas 1 a 4 só reproduzem com a composição oficial do TABNET; a lista do texto do artigo está errada')


# ---------------------------------------------------------------- 4. produto x TABNET / IBGE
def conferir_produto(sinistros):
    import importar_saude_vias as isv
    at = sinistros['atencao_territorial']
    ST = 'produto x TABNET/IBGE (2020-2024)'
    sim = isv.tabnet('sim/cnv/ext10pi.def', {'Linha': ['Região_de_Saúde_(CIR)'], 'Coluna': ['--Não-Ativa--'], 'Incremento': ['Óbitos_p/Residênc'],
                                              'Arquivos': [f'extpi{a % 100:02d}.dbf' for a in range(2020, 2025)], 'SGrupo_CID10': GRUPOS})
    sih = isv.tabnet('sih/cnv/frpi.def', {'Linha': ['Região_de_Saúde_(CIR)'], 'Coluna': ['--Não-Ativa--'], 'Incremento': ['Internações'],
                                           'Arquivos': [f'frpi{a % 100:02d}{m:02d}.dbf' for a in range(2020, 2025) for m in range(1, 13)], 'SGrupo_de_Causas': GRUPOS})
    por = lambda t: {slug(r[0][6:]): num(r[1]) for r in t[1:] if re.match(r'^\d{5} ', r[0])}  # noqa: E731
    s_sim, s_sih = por(sim), por(sih)
    div = []
    for k, r in at['regioes'].items():
        if s_sim.get(k) != r['obitos']:
            div.append(f'{r["nome"]} óbitos: painel {r["obitos"]} x TABNET {s_sim.get(k)}')
        if s_sih.get(k) != r['internacoes']:
            div.append(f'{r["nome"]} internações: painel {r["internacoes"]} x TABNET {s_sih.get(k)}')
    registrar(ST, 'Óbitos (SIM) e internações (SIH) por região de saúde: painel x TABNET ao vivo', '24 valores iguais',
              'iguais' if not div else '; '.join(div), 'ok' if not div else 'divergente')
    pop_api = json.loads(baixar('https://servicodados.ibge.gov.br/api/v3/agregados/4714/periodos/2022/variaveis/93?localidades=N6[N3[22]]'))
    pops = {s['localidade']['id'][:6]: int(s['serie']['2022']) for s in pop_api[0]['resultados'][0]['series']}
    s = json.load(open(os.path.join(ROOT, 'data', 'saude_municipios.json'), encoding='utf-8'))
    dif = [c for c, m in s['municipios'].items() if pops.get(c) != m['populacao_2022']]
    registrar(ST, 'População 2022 por município (IBGE, tabela 4714): painel x API ao vivo', f'{len(pops)} municípios iguais', 'iguais' if not dif and len(pops) == 224 else f'{len(dif)} diferentes',
              'ok' if not dif and len(pops) == 224 else 'divergente')
    registrar(ST, 'População do Piauí no Censo 2022 (artigo: 3.271.199) e número de municípios (224)', '3.271.199 e 224', f'{sum(pops.values()):,}'.replace(',', '.') + f' e {len(pops)}',
              'ok' if sum(pops.values()) == 3271199 and len(pops) == 224 else 'divergente')
    regs_p = {slug(m['regiao_de_saude'][6:]) for m in s['municipios'].values()}
    registrar(ST, 'Regiões de saúde do Piauí (artigo: 12)', 12, len(regs_p), 'ok' if len(regs_p) == 12 else 'divergente')


def escrever(sinistros_em):
    cont = {}
    for r in RESULTADOS:
        cont[r['status']] = cont.get(r['status'], 0) + 1
    saida = {'gerado_em': datetime.date.today().isoformat(), 'online': ONLINE,
             'referencia': 'Bastos FGT et al. Rev Bras Epidemiol 2026;29:e260044 (DOI 10.1590/1980-549720260044)',
             'fontes_consultadas': ['TABNET/DATASUS: SIH/SUS e SIM', 'IBGE: Censo 2022 (tabela 4714)', 'Banco Central: IGP-M (SGS 189)'],
             'resumo': cont, 'verificacoes': RESULTADOS}
    open(os.path.join(ROOT, 'data', 'verificacao_base.json'), 'w', encoding='utf-8', newline='').write(json.dumps(saida, ensure_ascii=False, indent=1))
    rot = {'ok': 'ok', 'divergente': 'DIVERGENTE', 'aviso': 'aviso', 'nao_reproduzido': 'não reproduzido'}
    linhas = ['# Verificação da base de dados', '',
              f'Gerado por `scripts/verificar_base.py{" --online" if ONLINE else ""}` em {saida["gerado_em"]}. Referência: {saida["referencia"]}.',
              'Fontes consultadas, todas citadas no artigo: ' + '; '.join(saida['fontes_consultadas']) + '.', '',
              '**Resumo:** ' + ', '.join(f'{rot[k]}: {v}' for k, v in sorted(cont.items())), '']
    pendentes = [r for r in RESULTADOS if r['status'] != 'ok']
    if pendentes:
        linhas += ['## Pontos de atenção', '']
        for r in pendentes:
            linhas.append(f'- **{rot[r["status"]]}** — {r["grupo"]}: {r["descricao"]}. Esperado: {r["esperado"]}. Obtido: {r["obtido"]}.' + (f' {r["nota"]}.' if r['nota'] else ''))
        linhas.append('')
    grupos = {}
    for r in RESULTADOS:
        grupos.setdefault(r['grupo'], []).append(r)
    linhas += ['## Todas as verificações', '']
    for g, rs in grupos.items():
        linhas += [f'### {g}', '', '| Verificação | Esperado | Obtido | Resultado |', '|---|---|---|---|']
        for r in rs:
            linhas.append(f'| {r["descricao"]} | {r["esperado"]} | {r["obtido"]} | {rot[r["status"]]} |'.replace('\n', ' '))
        linhas.append('')
    open(os.path.join(ROOT, 'VERIFICACAO_BASE.md'), 'w', encoding='utf-8', newline='').write('\n'.join(linhas))
    print('\n'.join(f'{rot[r["status"]]:>15}  {r["grupo"]} | {r["descricao"]}' for r in RESULTADOS if r['status'] != 'ok'))
    print('\nResumo:', {rot[k]: v for k, v in cont.items()})


if __name__ == '__main__':
    d = json.load(open(SINISTROS, encoding='utf-8'))
    conferir_artigo(d['estudo_morbidade_piaui_2010_2023'])
    consistencia_interna(d['estudo_morbidade_piaui_2010_2023'])
    if ONLINE:
        oficial = conferir_datasus(d['estudo_morbidade_piaui_2010_2023'])[0]
        conferir_codigo_macro(oficial)
        conferir_produto(d)
    escrever(d)
