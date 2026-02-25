// 글로벌 상태 변수 (수급 데이터를 쥐고 있는 역할)
let sentimentRawData = [];

// --- [공통] 차트 탭 전환 및 포맷팅 ---
function openTab(tabName) {
    const tabContents = document.getElementsByClassName("tab-content");
    for (let i = 0; i < tabContents.length; i++) tabContents[i].classList.remove("active");
    const tabBtns = document.getElementsByClassName("tab-btn");
    for (let i = 0; i < tabBtns.length; i++) tabBtns[i].classList.remove("active");
    const targetTab = document.getElementById(tabName);
    if(targetTab) targetTab.classList.add("active");
    if(event && event.currentTarget) event.currentTarget.classList.add("active");
}
const formatNum = (num) => new Intl.NumberFormat('ko-KR').format(Math.round(num));
const formatRatio = (num) => num.toFixed(1) + "%";

// --- [공통] 재무 차트 렌더링 엔진 ---
function drawChart(elementId, xData, datasets, title, yAxisTitle, isRatio = false) {
    const traces = datasets.map(dataset => ({
        x: xData, y: dataset.y, name: dataset.name, type: 'scatter', mode: 'lines+markers',
        hovertemplate: `<b>${dataset.name}</b><br>` + (isRatio ? '%{y:.1f}%' : '%{y:,.0f}') + '<extra></extra>',
        line: { width: 4, color: dataset.color, shape: 'spline' },
        marker: { size: 10, symbol: 'circle', line: { color: '#fff', width: 2 } }
    }));
    const layout = {
        title: { text: title, font: { color: '#f1f5f9', size: 18 } },
        xaxis: { title: "사업 연도", type: 'category', gridcolor: '#334155', tickfont: { color: '#94a3b8' } },
        yaxis: { title: yAxisTitle, gridcolor: '#334155', tickfont: { color: '#94a3b8' } },
        hovermode: 'x unified', margin: { t: 60, b: 50, l: 60, r: 30 },
        paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
        legend: { font: { color: '#f1f5f9' } }, hoverlabel: { bgcolor: '#1e293b', font: { color: '#f1f5f9' } }
    };
    if (document.getElementById(elementId)) Plotly.newPlot(elementId, traces, layout, { responsive: true, displayModeBar: false });
}

// --- [기능 1] 수급/공매도 슬라이싱 엔진 ---
function renderSentiment(period) {
    if (event && event.currentTarget) {
        document.querySelectorAll('.slice-btn').forEach(b => b.classList.remove('active'));
        event.currentTarget.classList.add('active');
    }
    if (!sentimentRawData || sentimentRawData.length === 0) return;

    let sliceCount = sentimentRawData.length;
    if (period === '1W') sliceCount = 5;
    else if (period === '1M') sliceCount = 20;

    const sliced = sentimentRawData.slice(-sliceCount);
    const dates = sliced.map(d => d.date);
    const shortVol = sliced.map(d => d.short_vol);
    const shortRatio = sliced.map(d => d.short_ratio);

    let fSum = 0, iSum = 0;
    const fCum = [], iCum = [];
    sliced.forEach(d => {
        fSum += d.foreigner_buy;
        iSum += d.inst_buy;
        fCum.push(fSum);
        iCum.push(iSum);
    });

    const xTickInterval = Math.ceil(sliced.length / 6);

    const shortingTraces = [
        { x: dates, y: shortVol, name: '공매도량', type: 'bar', marker: { color: 'rgba(100, 116, 139, 0.4)', line: { color: '#64748b', width: 1 } }, yaxis: 'y1', hovertemplate: '거래량: %{y:,.0f}주<extra></extra>' },
        { x: dates, y: shortRatio, name: '비중(%)', type: 'scatter', mode: 'lines', line: { color: '#ff4757', width: 3, shape: 'spline' }, yaxis: 'y2', hovertemplate: '비중: %{y:.1f}%<extra></extra>' }
    ];
    const shortingLayout = {
        title: { text: "⚠️ 일별 공매도 트래커", font: { color: '#f1f5f9', size: 15 }, y: 0.98, yanchor: 'top' },
        paper_bgcolor: 'transparent', plot_bgcolor: 'transparent', margin: { t: 60, b: 40, l: 50, r: 50 },
        legend: { orientation: 'h', y: 1.08, x: 0.5, xanchor: 'center', font: { color: '#94a3b8' } },
        hovermode: 'x unified',
        xaxis: { tickfont: { color: '#64748b' }, gridcolor: 'rgba(51, 65, 85, 0.2)', type: 'category', dtick: xTickInterval },
        yaxis: { title: '', tickfont: { color: '#64748b' }, gridcolor: 'rgba(51, 65, 85, 0.2)', zeroline: false },
        yaxis2: { title: '', tickfont: { color: '#ff4757' }, overlaying: 'y', side: 'right', showgrid: false, zeroline: false }
    };
    if(document.getElementById('chart-shorting')) Plotly.newPlot('chart-shorting', shortingTraces, shortingLayout, { responsive: true, displayModeBar: false });

    const smartTraces = [
        { x: dates, y: iCum, name: '기관', type: 'scatter', mode: 'lines', line: { color: '#2ed573', width: 3, shape: 'spline' }, hovertemplate: '기관: %{y:,.0f}주<extra></extra>' },
        { x: dates, y: fCum, name: '외국인', type: 'scatter', mode: 'lines', line: { color: '#1e90ff', width: 3, shape: 'spline' }, hovertemplate: '외국인: %{y:,.0f}주<extra></extra>' }
    ];
    const smartLayout = {
        title: { text: "🐳 스마트 머니 누적 수급", font: { color: '#f1f5f9', size: 15 }, y: 0.98, yanchor: 'top' },
        paper_bgcolor: 'transparent', plot_bgcolor: 'transparent', margin: { t: 60, b: 40, l: 60, r: 20 },
        legend: { orientation: 'h', y: 1.08, x: 0.5, xanchor: 'center', font: { color: '#94a3b8' } },
        hovermode: 'x unified',
        xaxis: { tickfont: { color: '#64748b' }, gridcolor: 'rgba(51, 65, 85, 0.2)', type: 'category', dtick: xTickInterval },
        yaxis: { title: '', tickfont: { color: '#64748b' }, gridcolor: 'rgba(51, 65, 85, 0.2)', zeroline: true, zerolinecolor: '#475569', zerolinewidth: 2 }
    };
    if(document.getElementById('chart-smartmoney')) Plotly.newPlot('chart-smartmoney', smartTraces, smartLayout, { responsive: true, displayModeBar: false });

    // 🌟 [신규 기능] 당일 실시간 수급 막대 차트 렌더링 엔진 (개인 수급 완벽 추가)
    const latestData = sliced[sliced.length - 1]; 
    
    if (latestData) {
        const now = new Date();
        const timeString = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
        document.getElementById('realtime-timestamp').innerText = `(기준: ${latestData.date} ${timeString})`;

        const retVal = latestData.retail_buy || 0; // 🌟 개인 데이터 추가
        const instVal = latestData.inst_buy || 0;
        const forVal = latestData.foreigner_buy || 0;

        const getColor = (val) => val > 0 ? '#ef4444' : '#3b82f6';

        const realtimeTraces = [{
            x: ['개인', '기관계', '외국인'], // 🌟 X축에 개인 추가
            y: [retVal, instVal, forVal],
            type: 'bar',
            text: [formatNum(retVal) + '주', formatNum(instVal) + '주', formatNum(forVal) + '주'],
            textposition: 'auto',
            marker: {
                color: [getColor(retVal), getColor(instVal), getColor(forVal)],
                line: { color: 'rgba(255,255,255,0.2)', width: 1 }
            },
            hovertemplate: '%{x}: %{y:,.0f}주<extra></extra>'
        }];

        const realtimeLayout = {
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent',
            margin: { t: 20, b: 40, l: 60, r: 20 },
            xaxis: { tickfont: { color: '#f1f5f9', size: 14 } },
            yaxis: { title: '순매수량 (주)', tickfont: { color: '#94a3b8' }, gridcolor: 'rgba(51, 65, 85, 0.2)', zeroline: true, zerolinecolor: '#475569', zerolinewidth: 2 },
            hovermode: 'closest'
        };

        if(document.getElementById('chart-realtime-bar')) {
            Plotly.newPlot('chart-realtime-bar', realtimeTraces, realtimeLayout, { responsive: true, displayModeBar: false });
        }
    }
}

// --- [기능 2] 대시보드 데이터 통신 엔진 (무한 루프 방지 및 안전장치 강화) ---
async function fetchAndRenderData(query) {
    const btn = document.getElementById("searchBtn");
    if(!btn) return;
    const originalText = btn.innerText;
    btn.innerText = "분석 중... ⚡";
    btn.style.opacity = "0.7";

    window.history.replaceState({}, '', `dashboard.html?query=${encodeURIComponent(query)}`);

    // 🌟 1. 타임아웃 함수 (5초 넘으면 강제로 에러 발생)
    const timeout = (ms) => new Promise((_, reject) => 
        setTimeout(() => reject(new Error("시간 초과")), ms)
    );

    try {
        // 🌟 2. 각 API 요청에 타임아웃 5초를 걸어 심부름꾼이 실종되는 것을 방지
        const pFinance = Promise.race([fetch(`http://127.0.0.1:8000/api/finance/${query}`).then(r => r.json()), timeout(5000)]);
        const pMarket = Promise.race([fetch(`http://127.0.0.1:8000/api/market/${query}`).then(r => r.json()), timeout(5000)]);
        const pSentiment = Promise.race([fetch(`http://127.0.0.1:8000/api/sentiment/${query}`).then(r => r.json()), timeout(5000)]);

        // --- 각각의 렌더링 로직 (성공한 데이터만 즉시 화면에 그림) ---
        pFinance.then(result => {
            const data = result.data;
            const years = data.map(d => d.year.toString());
            const rev = data.map(d => d.revenue);
            const op = data.map(d => d.operating_income);
            const net = data.map(d => d.net_income);
            const opCash = data.map(d => d.op_cash_flow);
            const fcf = data.map(d => d.fcf);
            const roe = data.map(d => d.roe);
            const opMargin = data.map(d => d.op_margin);
            const debt = data.map(d => d.debt_ratio);

            const lastIdx = data.length - 1;
            const prevIdx = Math.max(0, lastIdx - 1);
            const revYoy = ((rev[lastIdx] - rev[prevIdx]) / Math.abs(rev[prevIdx]||1)) * 100;
            const opYoy = ((op[lastIdx] - op[prevIdx]) / Math.abs(op[prevIdx]||1)) * 100;

            document.getElementById("kpi-rev").innerHTML = `${formatNum(rev[lastIdx])} <span style="font-size:16px; color:${revYoy >= 0 ? '#10b981' : '#ef4444'}">(${revYoy > 0 ? '▲' : '▼'} ${formatRatio(Math.abs(revYoy))})</span>`;
            document.getElementById("kpi-op").innerHTML = `${formatNum(op[lastIdx])} <span style="font-size:16px; color:${opYoy >= 0 ? '#10b981' : '#ef4444'}">(${opYoy > 0 ? '▲' : '▼'} ${formatRatio(Math.abs(opYoy))})</span>`;
            document.getElementById("kpi-roe").innerText = formatRatio(roe[lastIdx]);
            document.getElementById("kpi-debt").innerText = formatRatio(debt[lastIdx]);

            drawChart("chart-growth", years, [{ y: rev, name: "매출액", color: "#10b981" }, { y: op, name: "영업이익", color: "#3b82f6" }, { y: net, name: "당기순이익", color: "#8b5cf6" }], `${result.corp_name} 핵심 성장 추이`, "단위 (억원)");
            drawChart("chart-profit", years, [{ y: roe, name: "ROE", color: "#10b981" }, { y: opMargin, name: "영업이익률", color: "#3b82f6" }], `${result.corp_name} 수익률 추이`, "비율 (%)", true);
            drawChart("chart-stability", years, [{ y: debt, name: "부채비율", color: "#ef4444" }], `${result.corp_name} 재무 건전성 추이`, "비율 (%)", true);
            drawChart("chart-cashflow", years, [{ y: opCash, name: "영업활동현금흐름", color: "#3b82f6" }, { y: fcf, name: "잉여현금흐름(FCF)", color: "#f59e0b" }], `${result.corp_name} 현금 창출 능력`, "단위 (억원)");
        }).catch(e => console.error("재무 데이터 수집 지연/오류"));

        pMarket.then(marketResult => {
            const md = marketResult.data;
            document.getElementById("market-date").innerText = `(${marketResult.date} 종가 기준)`;
            document.getElementById("kpi-per").innerText = md.PER > 0 ? md.PER.toFixed(2) + "배" : "N/A";
            document.getElementById("kpi-pbr").innerText = md.PBR > 0 ? md.PBR.toFixed(2) + "배" : "N/A";
            document.getElementById("kpi-eps").innerText = formatNum(md.EPS) + "원";
            document.getElementById("kpi-div").innerText = md.DIV > 0 ? md.DIV.toFixed(2) + "%" : "배당없음";
        }).catch(e => console.error("시장 데이터 수집 지연/오류"));

        pSentiment.then(sentimentResult => {
            sentimentRawData = sentimentResult.data; 
            renderSentiment('3M'); 
        }).catch(e => console.error("수급 데이터 수집 지연/오류"));

        // 🌟 3. 모든 요청이 끝나거나 실패하더라도 최대 5초 후에는 버튼을 무조건 복구
        await Promise.allSettled([pFinance, pMarket, pSentiment]);

    } catch (error) {
        console.error("통합 통신 장애:", error);
    } finally {
        btn.innerText = originalText;
        btn.style.opacity = "1";
    }
}

document.addEventListener("DOMContentLoaded", () => {
    
    const searchInput = document.getElementById("searchInput");
    const searchBtn = document.getElementById("searchBtn");

    const executeSearch = () => {
        if (!searchInput) return; 
        const query = searchInput.value.trim();
        if (!query) return alert("기업명이나 종목코드를 입력해주세요!");
        window.location.href = `dashboard.html?query=${encodeURIComponent(query)}`;
    };

    if (searchBtn) searchBtn.addEventListener("click", executeSearch);
    if (searchInput) searchInput.addEventListener("keypress", (e) => { if (e.key === 'Enter') executeSearch(); });

    const urlParams = new URLSearchParams(window.location.search);
    const queryParam = urlParams.get('query');
    if (queryParam && window.location.pathname.includes('dashboard.html')) {
        if(searchInput) searchInput.value = queryParam;
        if(typeof fetchAndRenderData === "function") fetchAndRenderData(queryParam);
    }

    const runScreenerBtn = document.getElementById("runScreenerBtn");
    
    window.currentScreenerData = [];
    window.sortDirection = {};

    window.renderScreenerTable = (dataArray) => {
        const tbody = document.getElementById("result-tbody");
        if(!tbody) return;
        tbody.innerHTML = "";
        
        if (dataArray.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" style="padding: 20px; color: #94a3b8;">일치하는 종목이 없습니다.</td></tr>`;
            return;
        }

        dataArray.forEach(item => {
            const tr = document.createElement("tr");
            tr.style.cursor = "pointer";
            tr.onclick = () => window.location.href = `dashboard.html?query=${encodeURIComponent(item.stock_code)}`;
            
            tr.innerHTML = `
                <td style="font-weight: bold; color: #3b82f6;">${item.corp_name}</td>
                <td style="color: #cbd5e1; font-size: 13px;">${item.sector_name}</td>
                <td>${item.PER.toFixed(2)}</td>
                <td>${item.PBR.toFixed(2)}</td>
                <td>${item.ROE.toFixed(2)}%</td>
                <td style="color: #94a3b8;" title="${item.sector_name} 업종 평균 PER입니다.">${item.median_per.toFixed(2)}</td>
            `;
            tbody.appendChild(tr);
        });
    };

    window.sortTable = (key) => {
        if (!window.currentScreenerData || window.currentScreenerData.length === 0) return;
        
        window.sortDirection[key] = window.sortDirection[key] === 1 ? -1 : 1;
        const dir = window.sortDirection[key];

        const sortedData = [...window.currentScreenerData].sort((a, b) => {
            let valA = a[key];
            let valB = b[key];
            if (typeof valA === 'string') return valA.localeCompare(valB) * dir;
            return (valA - valB) * dir;
        });
        
        window.renderScreenerTable(sortedData);
    };

    const quickFilter = document.getElementById("quickFilter");
    if(quickFilter) {
        quickFilter.addEventListener("input", (e) => {
            const term = e.target.value.trim().toLowerCase();
            const filteredData = window.currentScreenerData.filter(item => 
                item.corp_name.toLowerCase().includes(term)
            );
            window.renderScreenerTable(filteredData);
            document.getElementById("result-count").innerText = filteredData.length;
        });
    }

    if (runScreenerBtn) {
        runScreenerBtn.addEventListener("click", async () => {
            runScreenerBtn.innerText = "탐색 중... ⏳";
            const reqBody = {
                min_roe: parseFloat(document.getElementById("filter-roe").value) || null,
                max_per: parseFloat(document.getElementById("filter-per").value) || null,
                max_pbr: parseFloat(document.getElementById("filter-pbr").value) || null,
                min_market_cap: (parseFloat(document.getElementById("filter-cap").value) * 100000000) || null,
                inst_buy_flag: document.getElementById("filter-inst").checked
            };

            try {
                const res = await fetch("http://127.0.0.1:8000/api/screener", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(reqBody)
                });
                if (!res.ok) throw new Error("스크리닝 API 통신 에러");
                
                const result = await res.json();
                window.currentScreenerData = result.data; 
                
                document.getElementById("screener-results").style.display = "block";
                document.getElementById("result-count").innerText = result.count;
                
                window.renderScreenerTable(window.currentScreenerData);

            } catch (e) {
                alert("스크리닝 중 오류가 발생했습니다.");
            } finally {
                runScreenerBtn.innerText = "조건 발굴 🚀";
            }
        });
    }
});