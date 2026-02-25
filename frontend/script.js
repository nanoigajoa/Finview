// 글로벌 상태 변수 (수급 데이터를 쥐고 있는 역할)
let sentimentRawData = [];

function openTab(tabName) {
    const tabContents = document.getElementsByClassName("tab-content");
    for (let i = 0; i < tabContents.length; i++) tabContents[i].classList.remove("active");
    const tabBtns = document.getElementsByClassName("tab-btn");
    for (let i = 0; i < tabBtns.length; i++) tabBtns[i].classList.remove("active");
    document.getElementById(tabName).classList.add("active");
    event.currentTarget.classList.add("active");
}
const formatNum = (num) => new Intl.NumberFormat('ko-KR').format(Math.round(num));
const formatRatio = (num) => num.toFixed(1) + "%";

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

// 🌟 신규: 기간별 슬라이싱 및 누적합 계산 엔진
// 🌟 신규: 세련된 디자인으로 업그레이드된 슬라이싱 및 렌더링 엔진
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

    // 🌟 X축 날짜 라벨이 너무 빽빽하지 않게 간격 자동 조절
    const xTickInterval = Math.ceil(sliced.length / 6);

    // [차트 1] 공매도 트래커 (투명도와 곡선의 조화)
    const shortingTraces = [
        {
            x: dates, y: shortVol, name: '공매도량', type: 'bar',
            marker: { color: 'rgba(100, 116, 139, 0.4)', line: { color: '#64748b', width: 1 } }, // 반투명 막대
            yaxis: 'y1', hovertemplate: '거래량: %{y:,.0f}주<extra></extra>'
        },
        {
            x: dates, y: shortRatio, name: '비중(%)', type: 'scatter', mode: 'lines', // 점(Marker) 제거
            line: { color: '#ff4757', width: 3, shape: 'spline' },
            yaxis: 'y2', hovertemplate: '비중: %{y:.1f}%<extra></extra>'
        }
    ];
    // [차트 1] 공매도 트래커 Layout 수정
    const shortingLayout = {
        title: {
            text: "⚠️ 일별 공매도 트래커",
            font: { color: '#f1f5f9', size: 15 },
            y: 0.98, // 🌟 [핵심] 1에 가까울수록 컨테이너의 맨 위로 딱 붙습니다.
            yanchor: 'top'
        },
        paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
        margin: { t: 60, b: 40, l: 50, r: 50 }, // 타이틀이 올라갈 공간(t)을 60으로 넉넉히 확보
        legend: { orientation: 'h', y: 1.08, x: 0.5, xanchor: 'center', font: { color: '#94a3b8' } }, // 범례가 타이틀을 침범하지 않게 살짝 내림
        hovermode: 'x unified',
        xaxis: { tickfont: { color: '#64748b' }, gridcolor: 'rgba(51, 65, 85, 0.2)', type: 'category', dtick: xTickInterval },
        yaxis: { title: '', tickfont: { color: '#64748b' }, gridcolor: 'rgba(51, 65, 85, 0.2)', zeroline: false },
        yaxis2: { title: '', tickfont: { color: '#ff4757' }, overlaying: 'y', side: 'right', showgrid: false, zeroline: false }
    };

    // [차트 2] 메이저 수급 (모던한 네온 라인과 Zero-line 강조)
    const smartTraces = [
        {
            x: dates, y: iCum, name: '기관', type: 'scatter', mode: 'lines',
            line: { color: '#2ed573', width: 3, shape: 'spline' }, // 형광 초록
            hovertemplate: '기관: %{y:,.0f}주<extra></extra>'
        },
        {
            x: dates, y: fCum, name: '외국인', type: 'scatter', mode: 'lines',
            line: { color: '#1e90ff', width: 3, shape: 'spline' }, // 맑은 파랑
            hovertemplate: '외국인: %{y:,.0f}주<extra></extra>'
        }
    ];
    const smartLayout = {
        title: {
            text: "🐳 스마트 머니 누적 수급",
            font: { color: '#f1f5f9', size: 15 },
            y: 0.98,         // 🌟 공매도 차트와 동일하게 맞춤
            yanchor: 'top'
        },
        paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
        margin: { t: 60, b: 40, l: 50, r: 50 },  // 🌟 공매도 차트와 동일하게 맞춤
        legend: {
            orientation: 'h',
            y: 1.08,          // 🌟 공매도 차트와 동일하게 맞춤
            x: 0.5,
            xanchor: 'center',
            font: { color: '#94a3b8' }
        },
        hovermode: 'x unified',
        xaxis: {
            tickfont: { color: '#64748b' },
            gridcolor: 'rgba(51, 65, 85, 0.2)',
            type: 'category',
            dtick: xTickInterval   // 🌟 공매도 차트와 동일하게 X축 간격 적용
        },
        yaxis: {
            title: '',
            tickfont: { color: '#64748b' },
            gridcolor: 'rgba(51, 65, 85, 0.2)',
            zeroline: true,
            zerolinecolor: '#475569',
            zerolinewidth: 2
        }
    };
    Plotly.newPlot('chart-shorting', shortingTraces, shortingLayout, { responsive: true, displayModeBar: false });
    Plotly.newPlot('chart-smartmoney', smartTraces, smartLayout, { responsive: true, displayModeBar: false });
}

// 메인 데이터 조회 함수
async function fetchAndRenderData(query) {
    const btn = document.getElementById("searchBtn");
    const originalText = btn.innerText;
    btn.innerText = "분석 중...";
    btn.style.opacity = "0.7";

    try {
        // [1] 재무 데이터 (기존 로직 유지)
        const financeResponse = await fetch(`http://127.0.0.1:8000/api/finance/${query}`);
        if (!financeResponse.ok) throw new Error("재무 데이터를 불러올 수 없습니다.");
        const result = await financeResponse.json();
        const corpName = result.corp_name;
        const data = result.data;

        window.history.replaceState({}, '', `dashboard.html?query=${encodeURIComponent(query)}`);

        // ... (기존 재무 KPI 및 차트 그리기 코드는 그대로 둡니다. 지면상 간략화 처리) ...
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
        const revYoy = ((rev[lastIdx] - rev[prevIdx]) / Math.abs(rev[prevIdx])) * 100;
        const opYoy = ((op[lastIdx] - op[prevIdx]) / Math.abs(op[prevIdx])) * 100;

        document.getElementById("kpi-rev").innerHTML = `${formatNum(rev[lastIdx])} <span style="font-size:16px; color:${revYoy >= 0 ? '#10b981' : '#ef4444'}">(${revYoy > 0 ? '▲' : '▼'} ${formatRatio(Math.abs(revYoy))})</span>`;
        document.getElementById("kpi-op").innerHTML = `${formatNum(op[lastIdx])} <span style="font-size:16px; color:${opYoy >= 0 ? '#10b981' : '#ef4444'}">(${opYoy > 0 ? '▲' : '▼'} ${formatRatio(Math.abs(opYoy))})</span>`;
        document.getElementById("kpi-roe").innerText = formatRatio(roe[lastIdx]);
        document.getElementById("kpi-debt").innerText = formatRatio(debt[lastIdx]);

        drawChart("chart-growth", years, [{ y: rev, name: "매출액", color: "#10b981" }, { y: op, name: "영업이익", color: "#3b82f6" }, { y: net, name: "당기순이익", color: "#8b5cf6" }], `${corpName} 핵심 성장 추이`, "단위 (억원)");
        drawChart("chart-profit", years, [{ y: roe, name: "ROE", color: "#10b981" }, { y: opMargin, name: "영업이익률", color: "#3b82f6" }], `${corpName} 수익률 추이`, "비율 (%)", true);
        drawChart("chart-stability", years, [{ y: debt, name: "부채비율", color: "#ef4444" }], `${corpName} 재무 건전성 추이`, "비율 (%)", true);
        drawChart("chart-cashflow", years, [{ y: opCash, name: "영업활동현금흐름", color: "#3b82f6" }, { y: fcf, name: "잉여현금흐름(FCF)", color: "#f59e0b" }], `${corpName} 현금 창출 능력`, "단위 (억원)");

        // [2] 시장 데이터 (PER, PBR 등)
        try {
            const marketResponse = await fetch(`http://127.0.0.1:8000/api/market/${query}`);
            if (marketResponse.ok) {
                const marketResult = await marketResponse.json();
                const md = marketResult.data;
                document.getElementById("market-date").innerText = `(${marketResult.date} 종가 기준)`;
                document.getElementById("kpi-per").innerText = md.PER > 0 ? md.PER.toFixed(2) + "배" : "N/A";
                document.getElementById("kpi-pbr").innerText = md.PBR > 0 ? md.PBR.toFixed(2) + "배" : "N/A";
                document.getElementById("kpi-eps").innerText = formatNum(md.EPS) + "원";
                document.getElementById("kpi-div").innerText = md.DIV > 0 ? md.DIV.toFixed(2) + "%" : "배당없음";
            }
        } catch (e) { console.warn("시장 데이터 오류", e); }

        // 🌟 [3] 수급 및 공매도 트래커 호출
        try {
            const sentimentResponse = await fetch(`http://127.0.0.1:8000/api/sentiment/${query}`);
            if (sentimentResponse.ok) {
                const sentimentResult = await sentimentResponse.json();
                sentimentRawData = sentimentResult.data; // 글로벌 변수에 캐싱
                renderSentiment('3M'); // 초기 화면은 3개월로 렌더링
            }
        } catch (e) { console.warn("수급 트래커 오류", e); }

    } catch (error) {
        console.error("Fetch 에러:", error);
        alert(`통신 에러가 발생했습니다: ${error.message}`);
    } finally {
        btn.innerText = originalText;
        btn.style.opacity = "1";
    }
}

document.addEventListener("DOMContentLoaded", () => {
    // [1] 기존 개별 종목 검색 로직
    const searchInput = document.getElementById("searchInput");
    const searchBtn = document.getElementById("searchBtn");

    const executeSearch = () => {
        const query = searchInput.value.trim();
        if (!query) return alert("기업명이나 종목코드를 입력해주세요!");
        if (window.location.pathname.endsWith('index.html') || window.location.pathname.endsWith('/')) {
            window.location.href = `dashboard.html?query=${encodeURIComponent(query)}`;
        } else {
            fetchAndRenderData(query);
        }
    };

    if (searchBtn) searchBtn.addEventListener("click", executeSearch);
    if (searchInput) searchInput.addEventListener("keypress", (e) => { if (e.key === 'Enter') executeSearch(); });

    const urlParams = new URLSearchParams(window.location.search);
    const queryParam = urlParams.get('query');
    if (queryParam && document.getElementById("dashboard-content")) {
        searchInput.value = queryParam;
        fetchAndRenderData(queryParam);
    }

    // 🌟 [2] 신규: 투 트랙 모드 전환 로직
    const modeSearch = document.getElementById("mode-search");
    const modeScreener = document.getElementById("mode-screener");
    const secSearch = document.getElementById("section-search");
    const secScreener = document.getElementById("section-screener");

    if (modeSearch && modeScreener) {
        modeSearch.addEventListener("click", () => {
            modeSearch.classList.add("active");
            modeScreener.classList.remove("active");
            secSearch.style.display = "flex";
            secScreener.style.display = "none";
        });
        modeScreener.addEventListener("click", () => {
            modeScreener.classList.add("active");
            modeSearch.classList.remove("active");
            secScreener.style.display = "block";
            secSearch.style.display = "none";
        });
    }

    // 🌟 [3] 신규: 스크리너 실행 및 테이블 렌더링 로직
    const runScreenerBtn = document.getElementById("runScreenerBtn");
    if (runScreenerBtn) {
        runScreenerBtn.addEventListener("click", async () => {
            // 입력된 값들을 JSON Payload로 포장
            const reqBody = {
                min_roe: parseFloat(document.getElementById("filter-roe").value) || null,
                max_per: parseFloat(document.getElementById("filter-per").value) || null,
                max_pbr: parseFloat(document.getElementById("filter-pbr").value) || null,
                min_market_cap: parseFloat(document.getElementById("filter-cap").value) * 100000000 || null, // 억원 -> 원 변환
                inst_buy_flag: document.getElementById("filter-inst").checked
            };

            runScreenerBtn.innerText = "탐색 중... ⏳";
            try {
                // POST 방식으로 백엔드 API 타격
                const res = await fetch("http://127.0.0.1:8000/api/screener", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(reqBody)
                });
                
                if (!res.ok) throw new Error("스크리닝 API 통신 에러");
                const result = await res.json();
                
                document.getElementById("screener-results").style.display = "block";
                document.getElementById("result-count").innerText = result.count;
                
                const tbody = document.getElementById("result-tbody");
                tbody.innerHTML = ""; // 기존 결과 초기화
                
                // 테이블 행 생성 및 클릭 이벤트(dashboard 연결) 부여
                result.data.forEach(item => {
                    const tr = document.createElement("tr");
                    tr.onclick = () => window.location.href = `dashboard.html?query=${encodeURIComponent(item.stock_code)}`;
                    tr.innerHTML = `
                        <td style="font-weight: bold; color: #3b82f6;">${item.corp_name}</td>
                        <td>${item.PER.toFixed(2)}</td>
                        <td>${item.PBR.toFixed(2)}</td>
                        <td>${item.ROE.toFixed(2)}%</td>
                        <td style="color: #94a3b8;">${item.median_per.toFixed(2)}</td>
                    `;
                    tbody.appendChild(tr);
                });
            } catch (e) {
                alert("스크리닝 중 오류가 발생했습니다.");
                console.error(e);
            } finally {
                runScreenerBtn.innerText = "조건 발굴 🚀";
            }
        });
    }
});