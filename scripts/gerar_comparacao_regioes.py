"""Monta a seção `comparacao_regioes_saude` de data/sinistros.json: gasto do SUS, óbitos e prevalência (taxa de internação)
por acidentes de transporte terrestre nas 12 regiões de saúde do Piauí, em dois períodos:
- 2010_2023: o do artigo (Bastos et al. 2026). Internações, óbitos hospitalares e valor pago vêm do SIH/SUS por residência, ano de
  processamento jan/2010-dez/2023 (reproduz os totais do artigo); óbitos gerais vêm do SIM; a prevalência é a taxa da Tabela 1 do artigo.
- 2020_2024: o do mapa do painel (SIM e SIH/SUS por residência); a prevalência é a taxa de internações de `atencao_territorial`.
O artigo não traz gasto por região de saúde (a Tabela 3 só chega às macrorregiões); os valores regionais vêm do TABNET, a mesma fonte.
Valores em reais nominais (sem correção pelo IGP-M: a correção do artigo não foi reproduzida, veja VERIFICACAO_BASE.md).
Também acrescenta ao `indice_busca` as palavras que levam o chat a essa seção. Precisa de internet (TABNET).
Uso: python scripts/gerar_comparacao_regioes.py   (rode depois de gerar_territorios.py e antes de gerar_perguntas.py)"""
import datetime, json, os, re, sys, unicodedata, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importar_saude_vias as isv   # noqa: E402
from prais_winsten import prais_winsten   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(ROOT, 'data', 'sinistros.json')
SAUDE = os.path.join(ROOT, 'data', 'saude_municipios.json')
GRUPOS = isv.GRUPOS_TERRESTRES

PERIODOS = {
    '2010_2023': {'anos': list(range(2010, 2024)), 'rotulo': '2010–2023 (período do artigo)'},
    '2020_2024': {'anos': list(range(2020, 2025)), 'rotulo': '2020–2024 (período do mapa)'},
}


def slug(s):
    s = ''.join(c for c in unicodedata.normalize('NFD', s.lower()) if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9]+', '_', s).strip('_')


def num(v):
    v = v.strip()
    return 0.0 if v in ('-', '', '...') else float(v.replace('.', '').replace(',', '.')) if ',' in v else float(v.replace('.', ''))


def br(v, casas=1):
    return f'{v:,.{casas}f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def por_regiao(tab):
    """Tabela Região de saúde x (nada) -> {slug: valor}; ignora a linha Total e as linhas sem código de região."""
    return {slug(r[0][6:]): num(r[1]) for r in tab[1:] if re.match(r'^\d{5} ', r[0])}


def consultar(anos):
    sih = lambda inc: por_regiao(isv.tabnet('sih/cnv/frpi.def', {   # noqa: E731
        'Linha': ['Região_de_Saúde_(CIR)'], 'Coluna': ['--Não-Ativa--'], 'Incremento': [inc],
        'Arquivos': [f'frpi{a % 100:02d}{m:02d}.dbf' for a in anos for m in range(1, 13)], 'SGrupo_de_Causas': GRUPOS}))
    sim = por_regiao(isv.tabnet('sim/cnv/ext10pi.def', {
        'Linha': ['Região_de_Saúde_(CIR)'], 'Coluna': ['--Não-Ativa--'], 'Incremento': ['Óbitos_p/Residênc'],
        'Arquivos': [f'extpi{a % 100:02d}.dbf' for a in anos], 'SGrupo_CID10': GRUPOS}))
    return sih('Internações'), sih('Óbitos'), sih('Valor_total'), sim


def calcular_tendencias(regioes):
    """VPA (variação percentual anual, regressão de Prais-Winsten sobre log10, como no artigo) 2010-2023 por região e para o estado:
    internações registradas e gasto registrado (SIH/SUS, por ano de processamento, como o artigo) e óbitos registrados (SIM, por ano do óbito).
    As séries são contagens anuais, o que equivale a taxas com população fixa; nas internações isso difere em menos de 0,5 ponto percentual
    ao ano da VPA da taxa na Tabela 1 do artigo (que usa a população projetada a cada ano). O gasto é corrigido pelo IGP-M (Banco Central,
    SGS 189): o valor de cada ano é levado de junho daquele ano a dezembro de 2023."""
    anos = list(range(2010, 2024))
    arq = [f'frpi{a % 100:02d}{m:02d}.dbf' for a in anos for m in range(1, 13)]

    def sih(inc):
        t = isv.tabnet('sih/cnv/frpi.def', {'Linha': ['Região_de_Saúde_(CIR)'], 'Coluna': ['Ano_processamento'], 'Incremento': [inc],
                                              'Arquivos': arq, 'SGrupo_de_Causas': GRUPOS})
        assert [int(a) for a in t[0][1:-1]] == anos, 'anos de processamento inesperados'
        return {slug(r[0][6:]): [num(x) for x in r[1:-1]] for r in t[1:] if re.match(r'^\d{5} ', r[0])}
    t = isv.tabnet('sim/cnv/ext10pi.def', {'Linha': ['Região_de_Saúde_(CIR)'], 'Coluna': ['Ano_do_Óbito'], 'Incremento': ['Óbitos_p/Residênc'],
                                            'Arquivos': [f'extpi{a % 100:02d}.dbf' for a in anos], 'SGrupo_CID10': GRUPOS})
    assert [int(a) for a in t[0][1:-1]] == anos, 'anos do óbito inesperados'
    sim = {slug(r[0][6:]): [num(x) for x in r[1:-1]] for r in t[1:] if re.match(r'^\d{5} ', r[0])}
    internacoes, valor = sih('Internações'), sih('Valor_total')
    req = urllib.request.Request('https://api.bcb.gov.br/dados/serie/bcdata.sgs.189/dados?formato=json&dataInicial=01/01/2009&dataFinal=31/12/2023',
                                 headers={'User-Agent': isv.UA['User-Agent'], 'Accept': 'application/json'})
    idx, acum = {}, 1.0
    for r in json.loads(urllib.request.urlopen(req, timeout=60).read()):
        _, mm, yy = r['data'].split('/')
        acum *= 1 + float(r['valor']) / 100
        idx[(int(yy), int(mm))] = acum
    fator = [idx[(2023, 12)] / idx[(a, 6)] for a in anos]

    def vpa(serie):
        pw = prais_winsten(serie, anos)
        t_ = 'Crescente' if pw['ic95_min'] > 0 else 'Decrescente' if pw['ic95_max'] < 0 else 'Estável'
        return {'vpa_pct': round(pw['vpa'], 2), 'ic95': [round(pw['ic95_min'], 2), round(pw['ic95_max'], 2)], 'tendencia': t_}

    def tres(i, o, v):
        return {'internacoes': vpa(i), 'obitos_sim': vpa(o), 'gasto_corrigido_igpm': vpa([a * f for a, f in zip(v, fator)])}
    soma = lambda S: [sum(S[k][i] for k in regioes) for i in range(len(anos))]   # noqa: E731
    out = {k: tres(internacoes[k], sim[k], valor[k]) for k in regioes}
    out['_estado'] = tres(soma(internacoes), soma(sim), soma(valor))
    return out


def ranks(valores):
    ordem = sorted(range(len(valores)), key=lambda i: valores[i])
    r = [0.0] * len(valores)
    i = 0
    while i < len(ordem):
        j = i
        while j + 1 < len(ordem) and valores[ordem[j + 1]] == valores[ordem[i]]:
            j += 1
        for k in range(i, j + 1):
            r[ordem[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(x, y):
    rx, ry = ranks(x), ranks(y)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    return cov / (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5


def montar(chave, d, base, tend=None):
    anos = d['anos']
    n_anos = len(anos)
    I, O, V, S = consultar(anos)
    pop, nomes, nivel, macro = base['pop'], base['nomes'], base['nivel'], base['macro']
    regs = {}
    for k in nomes:
        taxa_int = base['taxa_int_artigo'][k] if chave == '2010_2023' else base['taxa_int_mapa'][k]
        regs[k] = {
            'nome': nomes[k], 'macrorregiao': macro[k], 'nivel_atencao_mapa': nivel[k],
            'internacoes': int(I[k]), 'obitos_hospitalares': int(O[k]), 'obitos_sim': int(S[k]),
            'taxa_internacao_100mil': taxa_int,
            'taxa_obitos_sim_100mil_ano': round(S[k] / n_anos / pop[k] * 1e5, 1),
            'letalidade_hospitalar_pct': round(O[k] / I[k] * 100, 2) if I[k] else None,
            'gasto_total_reais': round(V[k], 2),
            'gasto_medio_por_internacao_reais': round(V[k] / I[k], 2) if I[k] else None,
            'gasto_por_habitante_ano_reais': round(V[k] / n_anos / pop[k], 2),
        }
    tot_i, tot_v, tot_s, tot_o = sum(I.values()), sum(V.values()), sum(S.values()), sum(O.values())
    for r in regs.values():
        r['pct_do_gasto_estadual'] = round(r['gasto_total_reais'] / tot_v * 100, 1)
        r['pct_das_internacoes_estaduais'] = round(r['internacoes'] / tot_i * 100, 1)
    pop_pi = sum(pop.values())
    estado = {
        'populacao_2022': pop_pi, 'internacoes': int(tot_i), 'obitos_hospitalares': int(tot_o), 'obitos_sim_em_regioes': int(tot_s),
        'taxa_internacao_100mil': base['taxa_int_estado'][chave], 'taxa_obitos_sim_100mil_ano': round(tot_s / n_anos / pop_pi * 1e5, 1),
        'letalidade_hospitalar_pct': round(tot_o / tot_i * 100, 2), 'gasto_total_reais': round(tot_v, 2),
        'gasto_medio_por_internacao_reais': round(tot_v / tot_i, 2), 'gasto_por_habitante_ano_reais': round(tot_v / n_anos / pop_pi, 2),
    }
    if tend:
        for k, r in regs.items():
            r['tendencia_anual'] = tend[k]
        estado['tendencia_anual'] = tend['_estado']
    # leitura pronta: o chat cita estes textos sem recalcular
    L = list(regs.values())
    topo = lambda campo, rev=True: sorted(L, key=lambda r: r[campo], reverse=rev)   # noqa: E731
    a, b, c, e = topo('gasto_total_reais')[0], topo('gasto_por_habitante_ano_reais')[0], topo('gasto_medio_por_internacao_reais')[0], topo('taxa_obitos_sim_100mil_ano')[0]
    leitura = [
        f'Maior gasto registrado do SUS com internações por sinistros de trânsito: {a["nome"]}, R$ {br(a["gasto_total_reais"] / 1e6, 1)} milhões '
        f'({br(a["pct_do_gasto_estadual"])}% do gasto estadual, com {br(a["pct_das_internacoes_estaduais"])}% das internações).',
        f'Maior gasto registrado por habitante por ano: {b["nome"]}, R$ {br(b["gasto_por_habitante_ano_reais"], 2)} (estado: R$ {br(estado["gasto_por_habitante_ano_reais"], 2)}).',
        f'Maior gasto registrado médio por internação: {c["nome"]}, R$ {br(c["gasto_medio_por_internacao_reais"], 2)} (estado: R$ {br(estado["gasto_medio_por_internacao_reais"], 2)}).',
        f'Maior taxa de óbitos registrados por sinistros de trânsito (SIM, residentes): {e["nome"]}, {br(e["taxa_obitos_sim_100mil_ano"])} por 100 mil hab. por ano (estado: {br(estado["taxa_obitos_sim_100mil_ano"])}).',
        f'Maior prevalência (taxa de internações registradas): {topo("taxa_internacao_100mil")[0]["nome"]}, {br(topo("taxa_internacao_100mil")[0]["taxa_internacao_100mil"])} por 100 mil hab. (estado: {br(estado["taxa_internacao_100mil"])}).',
    ]
    sub = [r['nome'] for r in L if r['taxa_obitos_sim_100mil_ano'] >= estado['taxa_obitos_sim_100mil_ano'] and r['taxa_internacao_100mil'] < 0.6 * estado['taxa_internacao_100mil']]
    if sub:
        leitura.append('Óbitos acima da média do estado com internações abaixo de 60% da média (sinal de possível falta de registro da causa externa no SIH, que também '
                       'reduz o gasto aparente): ' + ', '.join(sub) + '.')
    reg = lambda n: f'{n} região' if n == 1 else f'{n} regiões'   # noqa: E731
    if tend:
        rotulos = {'internacoes': 'internações registradas', 'obitos_sim': 'óbitos registrados (SIM)', 'gasto_corrigido_igpm': 'gasto registrado a preços constantes (IGP-M)'}
        for m, rot in rotulos.items():
            alta = [r for r in L if r['tendencia_anual'][m]['tendencia'] == 'Crescente']
            queda = [r for r in L if r['tendencia_anual'][m]['tendencia'] == 'Decrescente']
            maior = max(L, key=lambda r: r['tendencia_anual'][m]['vpa_pct'])
            menor = min(L, key=lambda r: r['tendencia_anual'][m]['vpa_pct'])
            e_ = estado['tendencia_anual'][m]
            leitura.append(f'Tendência 2010-2023 de {rot} (VPA por Prais-Winsten): estado {br(e_["vpa_pct"], 2)}% ao ano ({e_["tendencia"].lower()}); crescente em {reg(len(alta))}, '
                           f'decrescente em {reg(len(queda))} e estável em {reg(len(L) - len(alta) - len(queda))}; maior alta em {maior["nome"]} ({br(maior["tendencia_anual"][m]["vpa_pct"], 2)}% ao ano), '
                           f'menor em {menor["nome"]} ({br(menor["tendencia_anual"][m]["vpa_pct"], 2)}% ao ano).')

    def rho(x, y):
        return round(spearman([r[x] for r in L], [r[y] for r in L]), 2)
    corr = {
        'metodo': 'correlação de Spearman entre as 12 regiões (n pequeno; relação entre áreas, não entre pessoas)',
        'prevalencia_x_gasto_por_habitante': rho('taxa_internacao_100mil', 'gasto_por_habitante_ano_reais'),
        'prevalencia_x_taxa_de_obitos': rho('taxa_internacao_100mil', 'taxa_obitos_sim_100mil_ano'),
        'gasto_por_habitante_x_taxa_de_obitos': rho('gasto_por_habitante_ano_reais', 'taxa_obitos_sim_100mil_ano'),
    }
    return {'rotulo': d['rotulo'], 'anos': n_anos, 'estado': estado, 'regioes': regs, 'leitura': leitura, 'correlacao_entre_regioes': corr}


ADICOES_INDICE = {   # palavra (normalizada) -> caminhos que o chat deve enviar
    'gasto': ['comparacao_regioes_saude'], 'custo': ['comparacao_regioes_saude'], 'valor': ['comparacao_regioes_saude'],
    'despesa': ['comparacao_regioes_saude'], 'financ': ['comparacao_regioes_saude'], 'reais': ['comparacao_regioes_saude'],
    'orcament': ['comparacao_regioes_saude'], 'dinheiro': ['comparacao_regioes_saude'], 'per capita': ['comparacao_regioes_saude'],
    'vpa': ['comparacao_regioes_saude'], 'prais': ['comparacao_regioes_saude'],
    'prevalenc': ['comparacao_regioes_saude', 'estudo_morbidade_piaui_2010_2023.taxa_internacao_hospitalar_100mil_hab'],
    'incidenc': ['comparacao_regioes_saude', 'estudo_morbidade_piaui_2010_2023.taxa_internacao_hospitalar_100mil_hab'],
    'regiao': ['comparacao_regioes_saude'], 'regioes': ['comparacao_regioes_saude', 'estudo_morbidade_piaui_2010_2023.taxa_internacao_hospitalar_100mil_hab.por_regiao_de_saude'],
}


def anotar_estudo(d):
    """Registra no próprio estudo (para o chat e o painel) o que scripts/verificar_base.py --online encontrou ao conferir o artigo."""
    est = d['estudo_morbidade_piaui_2010_2023']
    est['conferencia_com_fontes_oficiais'] = (
        'Conferido contra TABNET/DATASUS (SIH/SUS e SIM), IBGE e Banco Central: os totais (80.251 internações, 1.866 óbitos, R$ 90,2 milhões, 392.047 dias), '
        'as séries por ano de processamento, os valores das Tabelas 2 a 4 e as VPAs de letalidade e permanência foram reproduzidos. '
        'Pontos de atenção estão em VERIFICACAO_BASE.md e nos campos "nota" abaixo.')
    nomes = {'semiarido': 'Semiárido', 'meio_norte': 'Meio-Norte', 'litoral': 'Litoral', 'cerrado': 'Cerrado'}
    comp = {}
    for k, v in d['planos_por_territorio']['regioes_de_saude'].items():
        comp.setdefault(v['macrorregiao'], []).append(v['nome'])
    est['composicao_macrorregioes'] = {
        'fonte': 'TABNET/DATASUS (macrorregião de saúde do Piauí); só esta composição reproduz as Tabelas 1 a 4 do artigo',
        'nota': 'O texto do artigo (Métodos) lista as regiões de cada macrorregião de outra forma; essa lista não confere com o TABNET. Use esta.',
        'macrorregioes': {m: sorted(r) for m, r in sorted(comp.items())}}
    vm = est['valor_medio_internacao_reais']
    vm['nota'] = (
        'O valor médio de R$ 1.123,92 e o total de R$ 90,2 milhões são NOMINAIS e foram reproduzidos exatamente no TABNET. A tendência decrescente (VPA -3,17%) '
        'vem do valor corrigido pelo IGP-M, que não foi reproduzido; em valores nominais o custo médio por internação subiu (cerca de +2,7% ao ano), e a queda corrigida pelo IGP-M foi confirmada em direção (entre -4,6% e -5,1% ao ano nos critérios testados com o IGP-M do Banco Central). Os valores corrigidos '
        'do artigo (R$ 128,0 milhões e R$ 1.659,40) não são compatíveis entre si (128,0 milhões ÷ 80.251 = R$ 1.595). A queda do custo médio não indica menor gasto real: '
        'o artigo a atribui à defasagem da tabela de procedimentos do SUS.')
    est['letalidade_hospitalar_pct']['por_faixa_etaria']['40_a_59_anos']['nota'] = (
        'O IC95 impresso no artigo (-2,55; 0,60) tem o limite inferior igual à VPA, provável erro de digitação; não cite o IC95 desta faixa.')
    est['letalidade_hospitalar_pct']['por_regiao_de_saude']['nota'] = (
        'As VPAs de Planície Litorânea, Tabuleiros do Alto Parnaíba, Vale do Canindé e Chapada Vale do Rio Itaim não puderam ser reproduzidas (há anos sem óbitos na série); '
        'as outras oito regiões foram reproduzidas exatamente.')
    ix = d['indice_busca']
    atual = ix.setdefault('macrorregiao', [])
    if 'estudo_morbidade_piaui_2010_2023.composicao_macrorregioes' not in atual:
        atual.append('estudo_morbidade_piaui_2010_2023.composicao_macrorregioes')
    for palavra in ('semiarido', 'meio norte', 'litoral', 'cerrado'):
        a = ix.setdefault(palavra, [])
        for c in ('estudo_morbidade_piaui_2010_2023.composicao_macrorregioes', 'estudo_morbidade_piaui_2010_2023.taxa_internacao_hospitalar_100mil_hab.por_macrorregiao'):
            if c not in a:
                a.append(c)


def main():
    d = json.load(open(JS, encoding='utf-8'))
    s = json.load(open(SAUDE, encoding='utf-8'))
    at = d['atencao_territorial']
    est = d['estudo_morbidade_piaui_2010_2023']
    pop = {}
    for m in s['municipios'].values():
        k = slug(m['regiao_de_saude'][6:])
        pop[k] = pop.get(k, 0) + m['populacao_2022']
    reg_plano = d['planos_por_territorio']['regioes_de_saude']
    base = {
        'pop': pop, 'nomes': {k: v['nome'] for k, v in at['regioes'].items()}, 'nivel': {k: v['nivel'] for k, v in at['regioes'].items()},
        'macro': {k: reg_plano[k]['macrorregiao'] for k in at['regioes']},
        'taxa_int_artigo': {k: v['valor'] for k, v in est['taxa_internacao_hospitalar_100mil_hab']['por_regiao_de_saude'].items()},
        'taxa_int_mapa': {k: v['taxa_internacoes'] for k, v in at['regioes'].items()},
        'taxa_int_estado': {'2010_2023': est['taxa_internacao_hospitalar_100mil_hab']['geral']['valor'], '2020_2024': at['estado']['taxa_internacoes']},
    }
    assert set(pop) == set(base['nomes']) == set(base['taxa_int_artigo']), 'chaves de região não batem'
    periodos = {}
    for chave, p in PERIODOS.items():
        print('TABNET:', p['rotulo'])
        tend = calcular_tendencias(list(base['nomes'])) if chave == '2010_2023' else None
        periodos[chave] = montar(chave, p, base, tend)
    secao = {
        'como_usar': ('Compara as 12 regiões de saúde em três medidas REGISTRADAS e relacionadas a sinistros de trânsito (acidentes de transporte terrestre, CID-10 V01-V89): prevalência '
                      '(taxa de internações registradas por 100 mil hab.), óbitos registrados (SIM) e gasto registrado do SUS com essas internações (SIH/SUS). Há dois períodos; não misture números de períodos diferentes. Cite os números e os textos de "leitura" como estão. '
                      'Em "regioes", cada região traz as três medidas e a participação no total do estado.'),
        'fonte': {
            'internacoes_obitos_hospitalares_gasto': 'SIH/SUS (TABNET/DATASUS, formulário frpi), V01-V89, por região de saúde de RESIDÊNCIA; "gasto" é o valor total pago pelo SUS nas AIH',
            'obitos_sim': 'SIM (TABNET/DATASUS, formulário ext10pi), óbitos por residência, V01-V89 (todos os óbitos, não só os hospitalares)',
            'populacao': 'IBGE, Censo 2022 (tabela 4714), somada por região de saúde',
            'prevalencia_2010_2023': 'taxa média de internação da Tabela 1 do artigo (Bastos et al. 2026; população projetada pelo Ministério da Saúde)',
            'prevalencia_2020_2024': 'taxa de internações de atencao_territorial (população do Censo 2022)',
            'tendencia_anual': 'só em 2010_2023: VPA (variação percentual anual) por regressão de Prais-Winsten sobre log10 de contagens anuais 2010-2023 (SIH/SUS por ano de processamento; SIM por ano do óbito), '
                               'com IC95% e tendência (Crescente/Decrescente se o IC95% não inclui zero; senão Estável); gasto corrigido pelo IGP-M do Banco Central (SGS 189), de junho de cada ano a dezembro de 2023',
            'consultado_em': datetime.date.today().isoformat(), 'gerado_por': 'scripts/gerar_comparacao_regioes.py'},
        'limites': [
            'Todos os números são REGISTRADOS e se referem a sinistros de trânsito (acidentes de transporte terrestre, CID-10 V01-V89): gasto = valor pago pelo SUS nas AIH registradas no SIH/SUS; '
            'óbitos = óbitos registrados no SIM; prevalência = internações registradas. O que não foi registrado, ou foi registrado com outra causa, não entra, e o gasto não inclui o '
            'que o SUS não pagou nem o setor privado. Chame sempre de "gasto registrado" e "óbitos registrados", nunca de gasto ou mortes totais.',
            'O artigo não traz gasto por região de saúde (a Tabela 3 só chega às macrorregiões); os valores regionais vêm do TABNET, a mesma fonte do artigo, e reproduzem os seus totais.',
            'Valores nominais, sem correção pelo IGP-M. O gasto médio por internação cai no artigo após a correção, mas em valores nominais ele subiu; a tabela de procedimentos do SUS '
            'não inclui o financiamento complementar de estados e municípios, então o gasto é subestimado.',
            'Gasto e internações dependem do registro da causa externa no SIH: regiões como Vale do Rio Guaribas e Chapada Vale do Rio Itaim registram poucas internações e podem '
            'estar subestimadas, o que reduz o gasto aparente. Por isso os óbitos do SIM são a medida mais completa.',
            'Gasto por habitante usa a população do Censo 2022 em todo o período. Entre Rios inclui Teresina, polo hospitalar do estado, mas as internações são por residência do paciente.',
            'Tendência anual (VPA): vem de contagens, não de taxas (a população anual projetada não está na base); nas internações isso difere em menos de 0,5 ponto percentual ao ano da VPA da '
            'Tabela 1 do artigo. A correção pelo IGP-M segue um critério próprio (junho de cada ano até dezembro de 2023), pois o do artigo não foi reproduzido. Em 2020_2024 não há VPA: '
            'cinco anos são pouco para a regressão.',
            'Dados por área (ecológicos): mostram associação entre regiões, não causa.'],
        'periodos': periodos,
    }
    d['comparacao_regioes_saude'] = secao
    anotar_estudo(d)
    ix = d['indice_busca']
    for palavra, caminhos in ADICOES_INDICE.items():
        atual = ix.setdefault(palavra, [])
        atual += [c for c in caminhos if c not in atual]
    internac = ix.setdefault('internac', [])
    internac += [c for c in ix.get('internacao', []) if c not in internac]   # "internações" casava só 'internac' (atencao_territorial.estado)
    open(JS, 'w', encoding='utf-8', newline='').write(json.dumps(d, ensure_ascii=False, indent=2))
    for chave, p in periodos.items():
        print(f'\n{p["rotulo"]}: estado {p["estado"]["internacoes"]} internações, R$ {br(p["estado"]["gasto_total_reais"] / 1e6, 2)} mi, {p["estado"]["obitos_sim_em_regioes"]} óbitos (SIM)')
        for t in p['leitura']:
            print('  -', t)
        print('  correlações:', p['correlacao_entre_regioes'])


if __name__ == '__main__':
    main()
