// Parse de percentual: suporta 12,95% ou 12.95%
function parsePercentage(str) {
    if (!str) return 0;
    let numStr = str.replace(/[^\d.,]/g, '');
    if (!numStr) return 0;
    
    // Se tem vírgula e ponto, a última ocorrência é decimal
    if (numStr.includes(',') && numStr.includes('.')) {
        const lastComma = numStr.lastIndexOf(',');
        const lastDot = numStr.lastIndexOf('.');
        if (lastComma > lastDot) {
            numStr = numStr.replace(/\./g, '').replace(',', '.');
        } else {
            numStr = numStr.replace(/,/g, '').replace('.', '.');
        }
    } else if (numStr.includes(',')) {
        numStr = numStr.replace(',', '.');
    }
    
    const num = parseFloat(numStr);
    return isNaN(num) ? 0 : num;
}

async function loadFGCData() {
    try {
        const response = await fetch('data/fgc_products.json');
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const produtos = await response.json();
        
        const tbody = document.getElementById('ranking-body');
        tbody.innerHTML = '';
        
        let totalNovos = 0;
        let rentSum = 0;
        let rentCount = 0;
        
        produtos.forEach(prod => {
            // Badges
            const ratingBadge = prod.rating === 'N/A' 
                ? `<span style="background:#f1f5f9;color:#374151;padding:2px 8px;border-radius:99px;font-size:0.75rem;font-weight:600;">N/A</span>`
                : `<span style="background:#fef9c3;color:#374151;padding:2px 8px;border-radius:99px;font-size:0.75rem;font-weight:600;">${prod.rating}</span>`;
            
            const indexadorBadge = `<span style="background:#dbeafe;color:var(--primary);padding:2px 8px;border-radius:99px;font-size:0.75rem;font-weight:600;">${prod.indexador.replace(/\s/g, '')}</span>`;
            
            // Data de primeira aparição
            let dataFormatada = '-';
            if (prod.data_primeira) {
                try {
                    const dataObj = new Date(prod.data_primeira);
                    dataFormatada = dataObj.toLocaleDateString('pt-BR');
                } catch (e) {
                    dataFormatada = prod.data_primeira;
                }
            }
            
            // Badge "Novo"
            const novoBadge = prod.is_new 
                ? `<span style="background:#dc2626;color:white;padding:2px 8px;border-radius:99px;font-size:0.75rem;font-weight:600; margin-left:5px;">NOVO</span>`
                : '';
            
            // Rentabilidade líquida para média
            const rentNum = parsePercentage(prod.rent_liquida);
            if (rentNum > 0) {
                rentSum += rentNum;
                rentCount++;
            }
            
            if (prod.is_new) totalNovos++;
            
            // Badge "FGC" se tem_fgc (verde neon vibrante)
            const fgcBadge = prod.tem_fgc 
                ? `<span style="background:#16a34a;color:white;padding:2px 8px;border-radius:99px;font-size:0.75rem;font-weight:600; margin-left:5px;">FGC</span>`
                : '';
            
            const tr = document.createElement('tr');
            tr.setAttribute('data-indexador', prod.indexador.replace(/\s/g, '').toLowerCase());
            tr.setAttribute('data-prazo', prod.prazo_tipo.toLowerCase());
            tr.innerHTML = `
                <td style="text-align:center;font-weight:700;color:var(--primary);">#${prod.rank}</td>
                <td>
                    <strong>${prod.produto}${novoBadge}${fgcBadge}</strong><br>
                    <small style="color:var(--muted)">${prod.emissor}</small>
                </td>
                <td style="text-align:center">${ratingBadge}</td>
                <td style="text-align:center">${indexadorBadge}</td>
                <td style="text-align:center">${prod.tipo}</td>
                <td style="text-align:center;color:#22c55e">${prod.rent_bruta}</td>
                <td style="text-align:center;color:#22c55e">${prod.rent_liquida}</td>
                <td style="text-align:center">${prod.minimo}</td>
                <td style="text-align:center">${prod.prazo}<br><small>${prod.prazo_tipo}</small></td>
                <td style="text-align:center; color: var(--muted); font-size: 0.9rem;">${dataFormatada}</td>
            `;
            tbody.appendChild(tr);
        });
        
        // Atualizar estatísticas
        document.getElementById('total-produtos').textContent = produtos.length;
        document.getElementById('produtos-novos').textContent = totalNovos;
        const rentMedia = rentCount ? (rentSum / rentCount).toFixed(2) + '%' : '-';
        document.getElementById('rent-media').textContent = rentMedia;
        
        setupFilters();
        
        // Atualizar footer com data
        try {
            const tsResponse = await fetch('data/last_updated.txt');
            const timestamp = await tsResponse.text();
            const dataObj = new Date(timestamp.trim());
            const dataFormatada = dataObj.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' });
            const lastUpdatedEl = document.getElementById('last-updated');
            if (lastUpdatedEl) {
                lastUpdatedEl.textContent = `Última atualização: ${dataFormatada}`;
            }
        } catch (e) {
            console.warn('Não foi possível carregar last_updated.txt:', e);
        }
        
    } catch (error) {
        console.error('Erro ao carregar dados FGC:', error);
        document.getElementById('ranking-body').innerHTML = '<tr><td colspan="10" style="text-align:center; padding: 2rem;">Erro ao carregar dados. Tente novamente mais tarde.</td></tr>';
    }
}

function setupFilters() {
    const indexadorFilter = document.getElementById('indexador-filter');
    const prazoFilter = document.getElementById('prazo-filter');
    
    function applyFilters() {
        const indexador = indexadorFilter.value.toLowerCase();
        const prazo = prazoFilter.value;
        const rows = document.querySelectorAll('#ranking-body tr');
        rows.forEach(row => {
            const cardIndexador = row.getAttribute('data-indexador').toLowerCase();
            const cardPrazo = row.getAttribute('data-prazo');
            // Indexador: match exato ou caso especial Pós-fixado (tudo que não é Pré-fixado)
            let matchIndexador = false;
            if (indexador === 'all') {
                matchIndexador = true;
            } else if (indexador === 'pós-fixado') {
                matchIndexador = cardIndexador !== 'pré-fixado';
            } else {
                matchIndexador = cardIndexador === indexador;
            }
            const matchPrazo = prazo === 'all' || cardPrazo === prazo;
            row.style.display = matchIndexador && matchPrazo ? '' : 'none';
        });
    }
    
    indexadorFilter.addEventListener('change', applyFilters);
    prazoFilter.addEventListener('change', applyFilters);
}

document.addEventListener('DOMContentLoaded', loadFGCData);
