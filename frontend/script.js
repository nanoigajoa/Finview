// 글로벌 상태 변수 (수급 데이터를 쥐고 있는 역할)
let sentimentRawData = [];

// 🌟 [버그 픽스] 차트 탭 전환 시 Plotly 강제 리사이즈 (공매도 차트 먹통 해결)
function openTab(tabName) {
    const tabContents = document.getElementsByClassName("tab-content");
    for (let i = 0; i < tabContents.length; i++) tabContents[i].classList.remove("active");
    
    const tabBtns = document.getElementsByClassName("tab-btn");
    for (let i = 0; i < tabBtns.length; i++) tabBtns[i].classList.remove("active");
    
    const targetTab = document.getElementById(tabName);
    if(targetTab) {
        targetTab.classList.add("active");
        
        // 🌟 핵심: 탭이 열리는 순간, 그 안에 숨어있던 모든 Plotly 차트에게 "너의 진짜 크기로 다시 그려라"라고 명령합니다.
        const charts = targetTab.querySelectorAll('.js-plotly-plot');
        charts.forEach(chart => Plotly.relayout(chart, {autosize: true}));
    }
    
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
    if (!sentimentRawData || sentimentRawData.length === 0) {
        // 빈 데이터일 때는 차트 영역을 초기화하고 안내 문구를 띄웁니다.
        ['chart-shorting','chart-smartmoney','chart-realtime-bar'].forEach(id=>{
            const el = document.getElementById(id);
            if(el) el.innerHTML = '<div style="padding:60px;color:#94a3b8;text-align:center;">수급 데이터가 없습니다.</div>';
        });
        return;
    }

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

    // 최신 데이터로 실시간 바 차트도 독립적으로 렌더링합니다 (차트가 없어도 전체 기능 중단 안됨)
    const latestData = sliced[sliced.length - 1];
    if (latestData) {
        const now = new Date();
        const timeString = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
        const tsEl = document.getElementById('realtime-timestamp');
        if(tsEl) tsEl.innerText = `(기준: ${latestData.date} ${timeString})`;

        const retVal = latestData.retail_buy || 0;
        const instVal = latestData.inst_buy || 0;
        const forVal = latestData.foreigner_buy || 0;
        const getColor = (val) => val > 0 ? '#ef4444' : '#3b82f6';

        const realtimeTraces = [{
            x: ['개인', '기관계', '외국인'],
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
            paper_bgcolor: 'transparent', plot_bgcolor: 'transparent', margin: { t: 20, b: 40, l: 60, r: 20 },
            xaxis: { tickfont: { color: '#f1f5f9', size: 14 } },
            yaxis: { title: '순매수량 (주)', tickfont: { color: '#94a3b8' }, gridcolor: 'rgba(51, 65, 85, 0.2)', zeroline: true, zerolinecolor: '#475569', zerolinewidth: 2 },
            hovermode: 'closest'
        };
        const barEl = document.getElementById('chart-realtime-bar');
        if(barEl) {
            Plotly.newPlot('chart-realtime-bar', realtimeTraces, realtimeLayout, { responsive: true, displayModeBar: false });
        }
    } else {
        const barEl = document.getElementById('chart-realtime-bar');
        if(barEl) barEl.innerHTML = '<div style="padding:60px;color:#94a3b8;text-align:center;">실시간 수급 데이터가 없습니다.</div>';
    }}

// --- [기능 2] 대시보드 데이터 통신 엔진 ---
async function fetchAndRenderData(query) {
    const btn = document.getElementById("searchBtn");
    if(!btn) return;
    const originalText = btn.innerText;
    btn.innerText = "분석 중... ⚡";
    btn.style.opacity = "0.7";

    window.history.replaceState({}, '', `dashboard.html?query=${encodeURIComponent(query)}`);

    // 상태 플래그
    window.metaStatuses = {finance:false, market:false, sentiment:false};
    // 배너 초기화
    const showDataWarning = () => {
        let msgs = [];
        if(window.metaStatuses.finance) msgs.push('재무 데이터 누락');
        if(window.metaStatuses.market) msgs.push('시장 지표 누락');
        if(window.metaStatuses.sentiment) msgs.push('수급/공매도 데이터 누락');
        let banner = document.getElementById('data-warning');
        if(!banner) {
            banner = document.createElement('div');
            banner.id = 'data-warning';
            banner.style.cssText = 'color:#ffcc00;background:#1e293b;padding:10px;border:1px solid #334155;margin-bottom:20px;';
            const container = document.getElementById('dashboard-content');
            if(container) container.prepend(banner);
        }
        if(msgs.length){
            banner.innerText = '⚠️ ' + msgs.join(' · ');
            banner.style.display = 'block';
        } else {
            banner.innerText = '';
            banner.style.display = 'none';
        }
    };
    showDataWarning();

    // 금융 데이터는 서버 내부 DART 호출이 느릴 수 있으므로
    // 타임아웃 없이 그대로 기다립니다. 시장/수급에는 5초 제한을 둡니다.
    const timeout = (ms) => new Promise((_, reject) => setTimeout(() => reject(new Error("시간 초과")), ms));

    try {
        const pFinance = fetch(`http://127.0.0.1:8000/api/finance/${query}`).then(r => r.json());
        const pMarket = Promise.race([fetch(`http://127.0.0.1:8000/api/market/${query}`).then(r => r.json()), timeout(5000)]);
        const pSentiment = Promise.race([fetch(`http://127.0.0.1:8000/api/sentiment/${query}`).then(r => r.json()), timeout(5000)]);

        pFinance.then(result => {
            const data = result.data;
            if(result.meta && result.meta.missing && result.meta.missing.length){
                window.metaStatuses.finance = true;
            }
            showDataWarning();
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
        }).catch(e => {console.error("재무 데이터 오류", e);
            window.metaStatuses.finance = true;
            showDataWarning();
        });

        pMarket.then(marketResult => {
            const md = (marketResult && marketResult.data) ? marketResult.data : {};
            if(!marketResult || !marketResult.meta || marketResult.meta.present === false) {
                window.metaStatuses.market = true;
            }
            showDataWarning();
            let dateStr = marketResult && marketResult.date ? `(${marketResult.date} 종가 기준)` : '';
            if(marketResult.meta && marketResult.meta.fallback) {
                dateStr += ' [← 배치데이터]';
            }
            document.getElementById("market-date").innerText = dateStr;
            document.getElementById("kpi-per").innerText = md.PER > 0 ? md.PER.toFixed(2) + "배" : "N/A";
            document.getElementById("kpi-pbr").innerText = md.PBR > 0 ? md.PBR.toFixed(2) + "배" : "N/A";
            document.getElementById("kpi-eps").innerText = formatNum(md.EPS) + "원";
            document.getElementById("kpi-div").innerText = md.DIV > 0 ? md.DIV.toFixed(2) + "%" : "배당없음";

            // 🌟 신규: 적정 주가 및 업사이드(+%) 렌더링 엔진
            const targetEl = document.getElementById("target-price");
            const upsideEl = document.getElementById("upside-percent");
            
            if (targetEl && upsideEl) {
                // 적자 기업(EPS가 0 이하)이거나 밸류에이션이 불가능한 경우 방어
                if (md.target_price > 0 && md.current_price > 0) {
                    targetEl.innerText = formatNum(md.target_price) + "원";
                    targetEl.style.color = "#ffffff";
                    
                    const upside = md.upside;
                    const color = upside > 0 ? "#10b981" : (upside < 0 ? "#ef4444" : "#94a3b8");
                    const sign = upside > 0 ? "+" : "";
                    
                    upsideEl.style.backgroundColor = `${color}20`;
                    upsideEl.style.color = color;
                    upsideEl.innerText = `${sign}${upside.toFixed(1)}% 기대`;
                    upsideEl.style.display = "inline-block";
                } else {
                    targetEl.innerText = "분석 불가 (적자 기업)";
                    targetEl.style.color = "#ef4444";
                    upsideEl.style.display = "none";
                }
            }
        }).catch(e=>{
            console.error('Market fetch failed', e);
            window.metaStatuses.market = true;
            showDataWarning();
        });

        pSentiment.then(sentimentResult => {
            sentimentRawData = sentimentResult.data || [];
            console.log("[sentiment] received", sentimentRawData.length, "records");
            if(sentimentResult.meta && sentimentResult.meta.count === 0) {
                window.metaStatuses.sentiment = true;
            }
            showDataWarning();
            renderSentiment('3M');
        }).catch(e => {
            console.error("수급 데이터 수집 지연/오류", e);
            window.metaStatuses.sentiment = true;
            showDataWarning();
            // 차트 영역을 모두 초기화하여 오류 화면을 사용자에게 알림
            ['chart-shorting','chart-smartmoney','chart-realtime-bar'].forEach(id=>{
                const el = document.getElementById(id);
                if(el) el.innerHTML = '<div style="padding:60px;color:#94a3b8;text-align:center;">수급 데이터 로드 실패</div>';
            });
        });

        await Promise.allSettled([pFinance, pMarket, pSentiment]);

    } catch (error) {
        console.error("통합 통신 장애:", error);
    } finally {
        btn.innerText = originalText;
        btn.style.opacity = "1";
    }
}

// 🌟 미니 막대그래프 렌더링 엔진 (너비 조정 포함)
const createMiniBar = (val, median) => {
    if (!val || !median || median <= 0 || val <= 0) return `<span style="color:#64748b;">N/A</span>`;
    
    const diff = ((val - median) / median) * 100;
    const color = diff < 0 ? "#10b981" : "#ef4444"; 
    const sign = diff > 0 ? "+" : "";
    const maxVal = Math.max(val, median);
    
    const valPct = Math.min((val / maxVal) * 100, 100);
    const medPct = Math.min((median / maxVal) * 100, 100);
    
    return `
        <div style="width: 100%; min-width: 110px; font-family: sans-serif; padding: 5px 0;">
            <div style="display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 4px;">
                <span><span style="color:#cbd5e1; font-weight:bold;">기업:</span> <span style="color:#fff;">${val.toFixed(2)}배</span></span>
                <span style="color: ${color}; font-weight: bold; background: rgba(255,255,255,0.05); padding: 2px 6px; border-radius: 4px;">${sign}${diff.toFixed(1)}%</span>
            </div>
            <div style="height: 6px; background: #334155; border-radius: 3px; overflow: hidden; margin-bottom: 8px;">
                <div style="width: ${valPct}%; background: ${color}; height: 100%; border-radius: 3px;"></div>
            </div>
            
            <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 4px; color:#94a3b8;">
                <span>업종: ${median.toFixed(2)}배</span>
            </div>
            <div style="height: 4px; background: #334155; border-radius: 2px; overflow: hidden;">
                <div style="width: ${medPct}%; background: #64748b; height: 100%; border-radius: 2px;"></div>
            </div>
        </div>
    `;
};

// 🌟 통합 컨트롤러 (이벤트 & 페이지네이션 엔진 탑재)
document.addEventListener("DOMContentLoaded", () => {
    
    // --- 1. [공통] 단일 종목 검색 엔진 ---
    const searchInput = document.getElementById("searchInput");
    const searchBtn = document.getElementById("searchBtn");

    const executeSearch = () => {
        if (!searchInput) return; 
        const query = searchInput.value.trim();
        if (!query) {
            alert("기업명이나 종목코드를 입력해주세요!");
            return;
        }
        window.location.href = `dashboard.html?query=${encodeURIComponent(query)}`;
    };

    if (searchBtn) searchBtn.addEventListener("click", executeSearch);
    if (searchInput) {
        searchInput.addEventListener("keypress", (e) => { 
            if (e.key === 'Enter') executeSearch(); 
        });
    }

    // --- 2. [대시보드 전용] ---
    const urlParams = new URLSearchParams(window.location.search);
    const queryParam = urlParams.get('query');
    if (queryParam && window.location.pathname.includes('dashboard.html')) {
        if(searchInput) searchInput.value = queryParam;
        if(typeof fetchAndRenderData === "function") fetchAndRenderData(queryParam);
    }

    // --- 3. [스크리너 전용] 멀티팩터 발굴 & 페이지네이션 엔진 ---
    const runScreenerBtn = document.getElementById("runScreenerBtn");
    
    window.currentScreenerData = [];
    window.sortDirection = {};
    
    // 🌟 페이지네이션 전용 상태 변수
    let currentPage = 1;
    const rowsPerPage = 50; // 한 페이지에 50개 종목 표출

    // 🌟 페이지 버튼을 그려주는 함수
    const renderPaginationControls = (totalItems) => {
        const container = document.getElementById("pagination-controls");
        if (!container) return;
        container.innerHTML = "";
        
        const totalPages = Math.ceil(totalItems / rowsPerPage);
        if (totalPages <= 1) return; // 1페이지 이하면 버튼 숨김

        // 이전 페이지 버튼
        const prevBtn = document.createElement("button");
        prevBtn.innerText = "◀ 이전";
        prevBtn.style.cssText = `padding: 6px 12px; border: 1px solid #334155; background: ${currentPage === 1 ? '#0f172a' : '#1e293b'}; color: ${currentPage === 1 ? '#475569' : '#f1f5f9'}; border-radius: 4px; cursor: ${currentPage === 1 ? 'default' : 'pointer'};`;
        prevBtn.disabled = currentPage === 1;
        prevBtn.onclick = () => { currentPage--; window.renderScreenerTable(window.currentScreenerData, false); };
        container.appendChild(prevBtn);

        // 현재 페이지 정보 표출
        const info = document.createElement("span");
        info.innerText = ` ${currentPage} / ${totalPages} `;
        info.style.cssText = "color: #94a3b8; font-size: 14px; margin: 0 10px; align-self: center;";
        container.appendChild(info);

        // 다음 페이지 버튼
        const nextBtn = document.createElement("button");
        nextBtn.innerText = "다음 ▶";
        nextBtn.style.cssText = `padding: 6px 12px; border: 1px solid #334155; background: ${currentPage === totalPages ? '#0f172a' : '#1e293b'}; color: ${currentPage === totalPages ? '#475569' : '#f1f5f9'}; border-radius: 4px; cursor: ${currentPage === totalPages ? 'default' : 'pointer'};`;
        nextBtn.disabled = currentPage === totalPages;
        nextBtn.onclick = () => { currentPage++; window.renderScreenerTable(window.currentScreenerData, false); };
        container.appendChild(nextBtn);
    };

    // 🌟 테이블 렌더링 함수 (페이지네이션 적용)
    window.renderScreenerTable = (dataArray, resetPage = true) => {
        if (resetPage) currentPage = 1; // 검색이나 정렬 시에는 무조건 1페이지로 리셋

        const tbody = document.getElementById("result-tbody");
        if(!tbody) return;
        tbody.innerHTML = "";
        
        if (dataArray.length === 0) {
            tbody.innerHTML = `<tr><td colspan="8" style="padding: 30px; text-align:center; color: #94a3b8; font-size: 16px;">조건에 완벽하게 일치하는 종목이 없습니다. 필터를 완화해 보세요.</td></tr>`;
            renderPaginationControls(0);
            return;
        }

        // 🌟 50개씩 잘라내는 로직
        const startIndex = (currentPage - 1) * rowsPerPage;
        const endIndex = startIndex + rowsPerPage;
        const paginatedData = dataArray.slice(startIndex, endIndex);

        paginatedData.forEach(item => {
            const tr = document.createElement("tr");
            tr.style.cursor = "pointer";
            tr.onclick = () => window.location.href = `dashboard.html?query=${encodeURIComponent(item.stock_code)}`;
            
            // 삭제된 '산업 평균' 컬럼을 빼고, 8열(Column) 체제로 렌더링
            tr.innerHTML = `
                <td style="font-weight: bold; color: #3b82f6; padding: 15px; vertical-align: middle;">${item.corp_name}</td>
                <td style="color: #cbd5e1; font-size: 13px; padding: 15px; vertical-align: middle;">${item.sector_name}</td>
                
                <td style="padding: 10px 15px; vertical-align: middle;">${createMiniBar(item.PER, item.median_per)}</td>
                <td style="padding: 10px 15px; vertical-align: middle;">${createMiniBar(item.PBR, item.median_pbr)}</td>
                <td style="padding: 10px 15px; vertical-align: middle;">${createMiniBar(item.PSR, item.median_psr)}</td>
                
                <td style="color: #f59e0b; font-weight: bold; text-align: center; vertical-align: middle; font-size: 15px;">${item.ROE.toFixed(1)}%</td>
                <td style="color: ${item.rev_cagr_3y > 10 ? '#10b981' : '#f1f5f9'}; text-align: center; vertical-align: middle; font-size: 15px;">${item.rev_cagr_3y.toFixed(1)}%</td>
                <td style="color: ${item.debt_ratio < 100 ? '#10b981' : '#ef4444'}; text-align: center; vertical-align: middle; font-size: 15px;">${item.debt_ratio.toFixed(1)}%</td>
            `;
            tbody.appendChild(tr);
        });

        // 테이블 그린 후 버튼 렌더링
        renderPaginationControls(dataArray.length);
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
        window.renderScreenerTable(sortedData, true); // 정렬하면 무조건 1페이지로 리셋
    };

    const quickFilter = document.getElementById("quickFilter");
    if(quickFilter) {
        quickFilter.addEventListener("input", (e) => {
            const term = e.target.value.trim().toLowerCase();
            const filteredData = window.currentScreenerData.filter(item => 
                item.corp_name.toLowerCase().includes(term)
            );
            window.renderScreenerTable(filteredData, true);
            document.getElementById("result-count").innerText = filteredData.length;
        });
    }

    if (runScreenerBtn) {
        runScreenerBtn.addEventListener("click", async () => {
            runScreenerBtn.innerText = "탐색 중... ⏳";
            
            const reqBody = {
                min_roe: parseFloat(document.getElementById("filter-roe")?.value) || null,
                max_per: parseFloat(document.getElementById("filter-per")?.value) || null,
                max_pbr: parseFloat(document.getElementById("filter-pbr")?.value) || null,
                min_market_cap: (parseFloat(document.getElementById("filter-cap")?.value) * 100000000) || null,
                inst_buy_flag: document.getElementById("filter-inst")?.checked || false,
                
                min_rev_cagr: parseFloat(document.getElementById("filter-rev-cagr")?.value) || null,
                min_op_cagr: parseFloat(document.getElementById("filter-op-cagr")?.value) || null,
                max_debt_ratio: parseFloat(document.getElementById("filter-debt")?.value) || null,
                ocf_pass_flag: document.getElementById("filter-ocf")?.checked || false,

                // 🌟 신규: 프론트엔드 통신망에 PEG 파라미터 완벽 이식
                max_peg: parseFloat(document.getElementById("filter-peg")?.value) || null, 

                relative_per_discount: parseFloat(document.getElementById("filter-rel-per")?.value) || null,
                relative_pbr_discount: parseFloat(document.getElementById("filter-rel-pbr")?.value) || null,
                relative_psr_discount: parseFloat(document.getElementById("filter-rel-psr")?.value) || null,
                relative_roe_excess: document.getElementById("filter-rel-roe")?.checked || false,
                relative_growth_excess: document.getElementById("filter-rel-growth")?.checked || false
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
                
                window.renderScreenerTable(window.currentScreenerData, true); // 검색하면 1페이지로 시작

            } catch (e) {
                console.error(e);
                alert("스크리닝 중 오류가 발생했습니다. 백엔드 상태를 확인해주세요.");
            } finally {
                runScreenerBtn.innerText = "조건 발굴 🚀";
            }
        });
    }
});