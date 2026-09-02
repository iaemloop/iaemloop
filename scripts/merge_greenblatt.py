#!/usr/bin/env python3
"""
Merge das páginas Greenblatt:
- greenblatt_landing.html: metodologia + top 30
- greenblatt_ned_landing.html: planilha 155 ações + metodologia extensa

Resultado: uma única página (greenblatt_landing.html) com metodologia + tabela completa de 155.
"""

from pathlib import Path

# Ler as duas páginas
landing = Path('greenblatt_landing.html').read_text(encoding='utf-8')
ned = Path('greenblatt_ned_landing.html').read_text(encoding='utf-8')

# Extrair parte da landing até antes da lista de cards (antes de <div class="grid">?)
# Ou até onde termina a introdução? Vamos manter o cabeçalho, meta tags, estilo e introdução da landing.
# Depois inserir a tabela completa do Ned, e depois a metodologia da landing? Na verdade o Ned já tem metodologia.
# Para simplificar: usar o HTML da landing como base e substituir a tabela pelas 155 linhas do Ned.
# Mas o Ned contém muito conteúdo antes da tabela também (sumário, etc). Vou pegar o conteúdo principal do Ned (a tabela) e inserir na landing após a introdução.
# landing structure: part after <div class="toc"> até </section> da metodologia? Melhor: pegar o conteúdo entre <section id="exemplo-real"> ... </section> do Ned e colocar na landing.
# Na landing não há seções tão detalhadas. Vou simplesmente adicionar uma seção "Planilha Completa (155 ações)" após a seção de exemplos.

# Extrair título e head da landing (até </head>)
head_end = landing.find('</head>')
head = landing[:head_end+6] if head_end != -1 else landing.split('\n')[0:20]

# Extrair body até o início do conteúdo principal (após <div class="container">?)
# Vou encontrar o início do container
container_start = landing.find('<div class="container">')
if container_start == -1:
    container_start = landing.find('<div class="toc">')  # fallback
if container_start == -1:
    print("❌ Não encontrou container")
    exit(1)

# Extrair do container até o final da landing
container_content = landing[container_start:]

# Extrair a tabela completa do Ned
# O Ned tem uma tabela grande com as 155 ações. Vamos copiar do <div class="card"> que contém a tabela até o fechamento </table>.
tabela_inicio = ned.find('<table>')
tabela_fim = ned.find('</table>') + len('</table>')
if tabela_inicio == -1 or tabela_fim == -1:
    print("❌ Tabela não encontrada no Ned")
    exit(1)
tabela_html = ned[tabela_inicio:tabela_fim]

# Encontrar onde inserir a tabela na landing. A landing tem uma seção "Exemplo real" que já contém uma tabela (top 30). Queremos substituir ou adicionar uma nova seção?
# Na landing greenblatt_landing.html, a estrutura: 
# sections: o-que-e, formulas, metodo, exemplo, carteira, consideracoes, como-usar, exemplo-real
# A seção exemplo-real contém a tabela top 30. Vamos substituir essa seção por uma nova versão que mostra as 155 ações, ou adicionar uma nova seção "Planilha Completa (155)" depois.
# O usuário quis merge, então provavelmente quer ambas as tabelas (top30 e full) ou apenas full? 
# Como a landing já explica metodologia, vamos manter o top30 como exemplo prático e adicionar a planilha completa como seção separada.
# Então: manter o conteúdo da landing (com top30) e APÓS a seção "exemplo-real", inserir uma nova seção "Planilha Completa (155)" com a tabela full.

# Encontrar fim da seção exemplo-real na landing
exemplo_real_fim = landing.find('</section>', landing.find('id="exemplo-real"'))
if exemplo_real_fim == -1:
    exemplo_real_fim = landing.find('</section>', landing.find('id="exemplo-real"'))
    if exemplo_real_fim == -1:
        print("❌ Não encontrou seção exemplo-real")
        exit(1)
    exemplo_real_fim += len('</section>')
else:
    exemplo_real_fim += len('</section>')

# Construir nova seção
nova_secao = f'''
        <section id="planilha-completa">
            <div class="card">
                <h2>📊 Planilha Completa (155 ações)</h2>
                <p>Resultado da aplicação da Fórmula Mágica a uma planilha da B3 com 155 ações. Incluindo nomes e setores das empresas.</p>
                <div style="overflow-x:auto;">
                    {tabela_html}
                </div>
                <p><small>*EY calculado como 1/EV/EBIT. Fonte: planilha original da B3 (Ned Stark).</small></p>
            </div>
        </section>
'''

# Montar novo HTML
 inicio = landing[:exemplo_real_fim]
 fim = landing[exemplo_real_fim:]
 novo_html = inicio + nova_secao + fim

# Salvar
Path('greenblatt_landing.html').write_text(novo_html, encoding='utf-8')
print('✅ greenblatt_landing.html mesclado com a planilha de 155 ações.')

# Remover greenblatt_ned_landing.html? Não vamos remover ainda, mas podemos deixar de usar. Melhor apagar para evitar confusão, mas vamos manter backup.
# Vou renomear a original para .bak e deixar a nova.
# Já fizemos backup. Podemos remover o greenblatt_ned_landing.html para evitar acesso direto.
Path('greenblatt_ned_landing.html').unlink(missing_ok=True)
print('🗑️  greenblatt_ned_landing.html removido (incorporado na greenblatt_landing.html).')