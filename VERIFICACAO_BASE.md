# Verificação da base de dados

Gerado por `scripts/verificar_base.py` em 2026-10-28. Referência: Bastos FGT et al. Rev Bras Epidemiol 2026;29:e260044 (DOI 10.1590/1980-549720260044).
Fontes consultadas, todas citadas no artigo: TABNET/DATASUS: SIH/SUS e SIM; IBGE: Censo 2022 (tabela 4714); Banco Central: IGP-M (SGS 189).

**Resumo:** aviso: 2, ok: 28

## Pontos de atenção

- **aviso** — consistência do artigo: Total corrigido (R$ 128,0 mi) / internações = valor médio corrigido (R$ 1.659,40). Esperado: 1659.4. Obtido: 1595.0. o artigo diz R$ 1.659,40, mas R$ 128,0 mi / 80.251 dá R$ 1.595: os dois valores corrigidos não são compatíveis entre si.
- **aviso** — consistência do artigo: Tabela 2, 40–59 anos: limite inferior do IC95 igual à própria VPA. Esperado: IC95 mín. < VPA < IC95 máx.. Obtido: VPA -2.55 (IC95 -2.55; 0.6). o artigo imprime -2,55 (-2,55; 0,60): provável erro de digitação do limite inferior (a VPA fica no centro do IC em escala log, o que daria algo perto de -5,6). A base repete o número do artigo; trate como não confiável.

## Todas as verificações

### artigo x base

| Verificação | Esperado | Obtido | Resultado |
|---|---|---|---|
| Tabela 1 (taxa de internação): linhas conferidas | todas iguais | 29 linhas idênticas ao artigo | ok |
| Tabela 2 (letalidade hospitalar): linhas conferidas | todas iguais | 29 linhas idênticas ao artigo | ok |
| Tabela 3 (valor médio por internação): linhas conferidas | todas iguais | 17 linhas idênticas ao artigo | ok |
| Tabela 4 (permanência média): linhas conferidas | todas iguais | 17 linhas idênticas ao artigo | ok |
| Tabelas 3 e 4 não trazem região de saúde | base sem custo/permanência por região | ok | ok |
| Texto do artigo: total de internações | 80251 | 80251 | ok |
| Texto do artigo: óbitos hospitalares | 1866 | 1866 | ok |
| Texto do artigo: total pago (R$) | 90200000 | 90200000 | ok |
| Texto do artigo: total corrigido IGP-M (R$) | 128000000 | 128000000 | ok |
| Texto do artigo: valor médio corrigido (R$) | 1659.4 | 1659.4 | ok |
| Texto do artigo: dias de permanência | 392047 | 392047 | ok |
| Texto do artigo: população 2022 | 3271199 | 3271199 | ok |
| Texto do artigo: ano com mais internações | 2016 | 2016 | ok |
| Texto do artigo: internações em 2016 | 7478 | 7478 | ok |
| Texto do artigo: taxa em 2016 | 230.3 | 230.3 | ok |
| Texto do artigo: ano com menos internações | 2012 | 2012 | ok |
| Texto do artigo: internações em 2012 | 2950 | 2950 | ok |
| Texto do artigo: taxa em 2012 | 91.8 | 91.8 | ok |
| DOI na citação (artigo: 10.1590/1980-549720260044) | 10.1590/1980-549720260044 | 44. DOI: 10.1590/1980-549720260044 | ok |

### consistência do artigo

| Verificação | Esperado | Obtido | Resultado |
|---|---|---|---|
| Soma das taxas por tipo de vítima = taxa geral (176,1) | 176.1 | 176.1 | ok |
| Razão homem/mulher (texto: 4,4 vezes) | 4.4 | 4.44 | ok |
| Razão motociclista/pedestre (texto: 12 vezes) | 12 | 12.0 | ok |
| Óbitos / internações = letalidade 2,3% | 2.3 | 2.33 | ok |
| Total pago / internações = valor médio (R$ 1.123,92) | 1123.92 | 1123.97 | ok |
| Total corrigido (R$ 128,0 mi) / internações = valor médio corrigido (R$ 1.659,40) | 1659.4 | 1595.0 | aviso |
| Dias / internações = permanência média 4,9 | 4.9 | 4.89 | ok |
| Tabela 2, 40–59 anos: limite inferior do IC95 igual à própria VPA | IC95 mín. < VPA < IC95 máx. | VPA -2.55 (IC95 -2.55; 0.6) | aviso |

### gráfico de comparação (Prais-Winsten)

| Verificação | Esperado | Obtido | Resultado |
|---|---|---|---|
| VPA das internações por região (contagens) x VPA da taxa (Tabela 1): maior diferença em pontos percentuais | até 0,6 ponto percentual | 0.50 | ok |
| Mesma classificação de tendência (crescente/estável/decrescente) que o artigo, nas 12 regiões | 12 iguais | 12 iguais | ok |
| VPA das internações do estado (contagens) x VPA da taxa do artigo (5,72) | 5.72 | 5.97 | ok |
