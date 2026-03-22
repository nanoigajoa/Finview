// 글로벌 상태 변수
let sentimentRawData = [];
let quarterlyCurrentYear = new Date().getFullYear() - 1;  // 기본값: 전년도 (예: 2025 → 2024)
window.currentQuery = null;

// API base: 같은 서버에서 서빙되면 상대경로, 파일로 직접 열면 localhost 폴백
const API_BASE = window.location.protocol === 'file:' ? 'http://127.0.0.1:8000' : '';

// 🌟 [버그 픽스] 차트 탭 전환 시 Plotly 강제 리사이즈 (공매도 차트 먹통 해결)
function openTab(tabName) {
    const tabContents = document.getElementsByClassName("tab-content");
    for (let i = 0; i < tabContents.length; i++) tabContents[i].classList.remove("active");

    const tabBtns = document.getElementsByClassName("tab-btn");
    for (let i = 0; i < tabBtns.length; i++) tabBtns[i].classList.remove("active");

    const targetTab = document.getElementById(tabName);
    if(targetTab) {
        targetTab.classList.add("active");
        const charts = targetTab.querySelectorAll('.js-plotly-plot');
        charts.forEach(chart => Plotly.relayout(chart, {autosize: true}));
    }

    if(event && event.currentTarget) event.currentTarget.classList.add("active");

    // 분기 탭 열릴 때 데이터 로드
    if (tabName === 'quarterly' && window.currentQuery) {
        fetchQuarterlyData(window.currentQuery, quarterlyCurrentYear);
    }
}

// ── 분기 차트 ──────────────────────────────────────────────────────────────
async function fetchQuarterlyData(query, year) {
    const revEl  = document.getElementById('chart-quarterly-rev');
    const opEl   = document.getElementById('chart-quarterly-op');
    if (!revEl || !opEl) return;
    revEl.innerHTML = '<div style="padding:40px;color:#94a3b8;text-align:center;">불러오는 중...</div>';
    opEl.innerHTML = '';
    try {
        const res = await fetch(`${API_BASE}/api/quarterly/${encodeURIComponent(query)}/${year}`);
        if (!res.ok) throw new Error('quarterly API 오류');
        const data = await res.json();
        renderQuarterlyChart(data);
    } catch (e) {
        revEl.innerHTML = `<div style="padding:40px;color:#ef4444;text-align:center;">분기 데이터 로드 실패: ${e.message}</div>`;
    }
}

function renderQuarterlyChart(data) {
    const revEl = document.getElementById('chart-quarterly-rev');
    const opEl  = document.getElementById('chart-quarterly-op');
    if (!revEl || !opEl || !data.quarters) return;

    const { h1, q3, q4, annual } = data.quarters;
    const labels = ['상반기(H1)', 'Q3', 'Q4', '연간합계'];
    const commonLayout = (title) => ({
        title: { text: title, font: { color: '#f1f5f9', size: 16 } },
        barmode: 'group',
        paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
        xaxis: { tickfont: { color: '#94a3b8' }, gridcolor: '#334155' },
        yaxis: { title: '억원', tickfont: { color: '#94a3b8' }, gridcolor: '#334155' },
        margin: { t: 50, b: 40, l: 60, r: 20 },
        legend: { font: { color: '#f1f5f9' } },
        hoverlabel: { bgcolor: '#1e293b', font: { color: '#f1f5f9' } }
    });

    const revVals = [h1.revenue, q3.revenue, q4.revenue, annual.revenue];
    const opVals  = [h1.op_income, q3.op_income, q4.op_income, annual.op_income];

    const barColors = ['#3b82f6', '#8b5cf6', '#f59e0b', '#10b981'];

    const makeTrace = (vals, name) => ({
        x: labels, y: vals, name,
        type: 'bar',
        marker: { color: barColors },
        hovertemplate: '%{x}: %{y:,.1f}억<extra></extra>',
        text: vals.map(v => v !== 0 ? v.toFixed(0) : ''),
        textposition: 'outside',
        textfont: { color: '#94a3b8', size: 11 }
    });

    Plotly.newPlot(revEl, [makeTrace(revVals, '매출액')],
        commonLayout(`${data.corp_name} ${data.year}년 분기별 매출액`),
        { responsive: true, displayModeBar: false });

    Plotly.newPlot(opEl, [makeTrace(opVals, '영업이익')],
        commonLayout(`${data.corp_name} ${data.year}년 분기별 영업이익`),
        { responsive: true, displayModeBar: false });
}

function initQuarterlyYearButtons(query) {
    const container = document.getElementById('quarterly-year-btns');
    if (!container) return;
    const currentYear = new Date().getFullYear();
    const years = [currentYear - 1, currentYear - 2, currentYear - 3, currentYear - 4];
    quarterlyCurrentYear = years[0];
    container.innerHTML = '';
    years.forEach((yr, idx) => {
        const btn = document.createElement('button');
        btn.innerText = yr + '년';
        btn.style.cssText = `padding:6px 14px; border-radius:6px; border:1px solid #334155; cursor:pointer; font-size:13px;
            background:${idx === 0 ? '#3b82f6' : '#1e293b'}; color:${idx === 0 ? '#fff' : '#94a3b8'};`;
        btn.dataset.year = yr;
        btn.onclick = () => {
            document.querySelectorAll('#quarterly-year-btns button').forEach(b => {
                b.style.background = '#1e293b'; b.style.color = '#94a3b8';
            });
            btn.style.background = '#3b82f6'; btn.style.color = '#fff';
            quarterlyCurrentYear = yr;
            fetchQuarterlyData(query, yr);
        };
        container.appendChild(btn);
    });
}

const formatNum = (num) => new Intl.NumberFormat('ko-KR').format(Math.round(num));
const formatRatio = (num) => num.toFixed(1) + "%";

// 데이터 소스 배지 렌더링
function renderSourceBadge(type, sourceInfo) {
    const el = document.getElementById(`badge-${type}`);
    if (!el || !sourceInfo) return;
    const bar = document.getElementById('data-sources-bar');
    if (bar) bar.style.display = 'flex';
    const status = sourceInfo.status || 'missing';
    const from = sourceInfo.from || '';
    const note = sourceInfo.note || '';
    const colors = { ok: '#10b981', partial: '#f59e0b', missing: '#ef4444' };
    const icons  = { ok: '✓', partial: '⚠', missing: '✗' };
    const fromLabels = {
        dart_realtime: 'DART', realtime: '실시간', screener_quality: '집계캐시',
        cache: '캐시', none: '없음',
        trading_value: 'KRX', trading_volume: 'KRX', naver_frgn: '네이버',
    };
    const color = colors[status] || '#94a3b8';
    const icon  = icons[status]  || '?';
    const fromLabel = fromLabels[from] || from;
    const labels = { finance: '재무', market: '시장', sentiment: '수급' };
    const title = note ? ` title="${note}"` : '';
    el.innerHTML = `${labels[type] || type}: <span style="color:${color};font-weight:bold;"${title}>${icon} ${fromLabel}</span>`;
}

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
        const tsEl = document.getElementById('realtime-timestamp');
        // P1: 전일 종가 기준 데이터 — 브라우저 현재 시각 혼용 제거
        if(tsEl) tsEl.innerText = `(기준: ${latestData.date} 종가 기준)`;

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
    window.currentQuery = query;
    initQuarterlyYearButtons(query);

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
        const pFinance = Promise.race([fetch(`${API_BASE}/api/finance/${query}`).then(r => r.json()), timeout(30000)]);
        const pMarket = Promise.race([fetch(`${API_BASE}/api/market/${query}`).then(r => r.json()), timeout(15000)]);
        const pSentiment = Promise.race([fetch(`${API_BASE}/api/sentiment/${query}`).then(r => r.json()), timeout(15000)]);

        pFinance.then(result => {
            const data = result.data;
            const finSrc = result.meta?.sources?.finance;
            renderSourceBadge('finance', finSrc);
            if (finSrc && finSrc.status !== 'ok') {
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
        }).catch(e => {
            console.error("재무 데이터 오류", e);
            window.metaStatuses.finance = true;
            renderSourceBadge('finance', {status: 'missing', from: 'none', note: e.message});
            showDataWarning();
        });

        pMarket.then(marketResult => {
            const md = (marketResult && marketResult.data) ? marketResult.data : {};
            const mktSrc = marketResult?.meta?.sources?.market;
            renderSourceBadge('market', mktSrc);
            if (!mktSrc || mktSrc.status === 'missing') {
                window.metaStatuses.market = true;
            }
            showDataWarning();
            let dateStr = marketResult && marketResult.date ? `(${marketResult.date} 종가 기준)` : '';
            if(marketResult?.meta?.fallback || mktSrc?.from === 'cache') {
                dateStr += ' [← 배치데이터]';
            }
            document.getElementById("market-date").innerText = dateStr;
            document.getElementById("kpi-per").innerText = md.PER > 0 ? md.PER.toFixed(2) + "배" : "N/A";
            document.getElementById("kpi-pbr").innerText = md.PBR > 0 ? md.PBR.toFixed(2) + "배" : "N/A";
            // EPS: 적자 기업 표시
            document.getElementById("kpi-eps").innerText = md.EPS_negative ? "적자" : (formatNum(md.EPS) + "원");
            document.getElementById("kpi-div").innerText = md.DIV > 0 ? md.DIV.toFixed(2) + "%" : "배당없음";

            // TTM PER: 연간 PER 대비 색상 (TTM PER < 연간 PER → 이익 증가 신호 → 초록)
            const ttmPerEl = document.getElementById("kpi-ttm-per");
            if (ttmPerEl) {
                if (md.ttm_per > 0) {
                    ttmPerEl.innerText = md.ttm_per.toFixed(2) + "배";
                    ttmPerEl.style.color = (md.PER > 0 && md.ttm_per < md.PER) ? "#10b981" : "#ef4444";
                } else {
                    ttmPerEl.innerText = "N/A";
                    ttmPerEl.style.color = "";
                }
            }

            // Graham Number
            const grahamEl = document.getElementById("kpi-graham");
            if (grahamEl)
                grahamEl.innerText = md.graham > 0 ? formatNum(md.graham) + "원" : "N/A";

            // 적정 주가 및 업사이드(+%) 렌더링
            const targetEl = document.getElementById("target-price");
            const upsideEl = document.getElementById("upside-percent");

            if (targetEl && upsideEl) {
                if (md.target_price > 0 && md.current_price > 0) {
                    targetEl.innerText = formatNum(md.target_price) + "원";
                    targetEl.style.color = "#ffffff";
                    // tooltip: TTM EPS 기반 여부 명시
                    targetEl.title = md.ttm_available
                        ? `TTM EPS(${formatNum(md.ttm_eps)}원) × 섹터PER`
                        : `연간 EPS(${formatNum(md.EPS)}원) × 섹터PER`;

                    const upside = md.upside;
                    const color = upside > 0 ? "#10b981" : (upside < 0 ? "#ef4444" : "#94a3b8");
                    const sign = upside > 0 ? "+" : "";
                    upsideEl.style.backgroundColor = `${color}20`;
                    upsideEl.style.color = color;
                    upsideEl.innerText = `${sign}${upside.toFixed(1)}% 기대`;
                    upsideEl.style.display = "inline-block";
                } else {
                    targetEl.innerText = md.EPS_negative ? "분석 불가 (적자 기업)" : "분석 불가";
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
            const sentSrc = sentimentResult?.meta?.sources?.sentiment;
            renderSourceBadge('sentiment', sentSrc);
            if (!sentSrc || sentSrc.status === 'missing') {
                window.metaStatuses.sentiment = true;
            } else if (sentSrc.status === 'partial') {
                // partial은 경고 배너 대신 배지로만 표시
            }
            showDataWarning();
            renderSentiment('3M');
        }).catch(e => {
            console.error("수급 데이터 수집 지연/오류", e);
            window.metaStatuses.sentiment = true;
            renderSourceBadge('sentiment', {status: 'missing', from: 'none', note: e.message});
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
                
                <td style="padding: 10px 15px; vertical-align: middle;">${createMiniBar(item.PER, item.sector_per)}</td>
                <td style="padding: 10px 15px; vertical-align: middle;">${createMiniBar(item.PBR, item.sector_pbr)}</td>
                <td style="padding: 10px 15px; vertical-align: middle;">${createMiniBar(item.PSR, item.sector_psr)}</td>
                
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
                const res = await fetch(`${API_BASE}/api/screener`, {
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